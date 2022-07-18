#include <folly/FileUtil.h>
#include <proxygen/httpserver/samples/servermigration/app/common/Utils.h>
#include <proxygen/httpserver/samples/servermigration/app/server/MigrationManagementInterface.h>

namespace quic::samples::servermigration {

void MigrationManagementInterface::resetMigrationState() {
  migrationInProgress_ = false;
  transportsReady_ = false;
  networkSwitched_ = false;
  numberOfTransportsReady_ = 0;
  numberOfTransportsMigrated_ = 0;
}

MigrationManagementInterface::MigrationManagementInterface(
    std::string host,
    uint16_t port,
    folly::EventBase *evb,
    std::shared_ptr<QuicServer> quicServer)
    : host_(std::move(host)),
      port_(port),
      evb_(evb),
      quicServer_(std::move(quicServer)) {
  folly::SocketAddress address(host_, port_);
  socket_ = std::make_unique<folly::AsyncUDPSocket>(evb_);
  socket_->bind(address);
  socket_->setErrMessageCallback(this);
}

void MigrationManagementInterface::start() {
  LOG(INFO) << "Starting management interface at: "
            << socket_->address().describe();
  socket_->resumeRead(this);
}

void MigrationManagementInterface::onHandshakeFinished(
    folly::SocketAddress clientAddress,
    quic::ConnectionId serverConnectionId,
    folly::Optional<std::unordered_set<ServerMigrationProtocol>>
        negotiatedProtocols) noexcept {
  std::string negotiatedProtocolsString =
      (negotiatedProtocols && !negotiatedProtocols->empty())
          ? migrationProtocolsToString(negotiatedProtocols.value())
          : "none";
  VLOG(1) << fmt::format(
      "New client connected to the server, with address={}, transport CID={}, "
      "negotiated protocols={}",
      clientAddress.describe(),
      serverConnectionId.hex(),
      negotiatedProtocolsString);

  std::lock_guard<std::mutex> guard(migrationMutex_);
  if (networkSwitched_) {
    // New client is connecting while the other transports are completing
    // the server migration process (path validation) and the management
    // interface is keeping track of the calls to onServerMigrationCompleted().
    // To not interfere with this mechanism, consider the new transport as a
    // successfully migrated transport, at least from the point of view of
    // the related counter. Note that both numberOfTransportsMigrated_ and
    // transports_.size() are increased within this call.
    ++numberOfTransportsMigrated_;
  }
  transports_.emplace(serverConnectionId, TransportMigrationState::NOT_READY);
}

void MigrationManagementInterface::onClientMigrationDetected(
    quic::ConnectionId serverConnectionId,
    folly::SocketAddress newClientAddress) noexcept {
  VLOG(1) << fmt::format(
      "Client migration detected. Involved server transport={}, "
      "new client address={}",
      serverConnectionId.hex(),
      newClientAddress.describe());
}

void MigrationManagementInterface::onConnectionClose(
    quic::ConnectionId serverConnectionId) noexcept {
  VLOG(1) << fmt::format("Transport {} closed", serverConnectionId.hex());
  std::lock_guard<std::mutex> guard(migrationMutex_);

  if (!migrationInProgress_) {
    transports_.erase(serverConnectionId);
    return;
  }

  if (networkSwitched_) {
    // onNetworkSwitch() has been called on the server.
    if (transports_[serverConnectionId] == TransportMigrationState::COMPLETED) {
      --numberOfTransportsMigrated_;
    }
    transports_.erase(serverConnectionId);
    if (numberOfTransportsMigrated_ == transports_.size()) {
      VLOG(1) << "Server migration completed";
      resetMigrationState();
    }
    return;
  }

  // onImminentServerMigration() has been called on the server.
  if (transports_[serverConnectionId] == TransportMigrationState::READY) {
    --numberOfTransportsReady_;
  }
  transports_.erase(serverConnectionId);
  if (numberOfTransportsReady_ == transports_.size() && !transportsReady_) {
    VLOG(1) << "Server ready for migration";
    transportsReady_ = true;
  }
}

void MigrationManagementInterface::onServerMigrationFailed(
    ConnectionId serverConnectionId, ServerMigrationError error) noexcept {
  // onServerMigrationFailed() is always followed by onConnectionClose(),
  // so the operations involving the map are done inside the latter.
  LOG(ERROR) << fmt::format(
      "Transport {} failed server migration with "
      "error={}",
      serverConnectionId.hex(),
      serverMigrationErrorToString(error));
}

void MigrationManagementInterface::onServerMigrationReady(
    ConnectionId serverConnectionId) noexcept {
  VLOG(1) << fmt::format("Transport {} ready for server migration",
                         serverConnectionId.hex());
  std::lock_guard<std::mutex> guard(migrationMutex_);
  transports_[serverConnectionId] = TransportMigrationState::READY;
  ++numberOfTransportsReady_;
  if (numberOfTransportsReady_ == transports_.size()) {
    migrationReadyTime_ = std::chrono::steady_clock::now();
    transportsReady_ = true;
    VLOG(1) << "Server ready for migration";
  }
}

void MigrationManagementInterface::onServerMigrationCompleted(
    ConnectionId serverConnectionId) noexcept {
  VLOG(1) << fmt::format("Transport {} completed the migration",
                         serverConnectionId.hex());
  std::lock_guard<std::mutex> guard(migrationMutex_);
  transports_[serverConnectionId] = TransportMigrationState::COMPLETED;
  ++numberOfTransportsMigrated_;
  if (numberOfTransportsMigrated_ == transports_.size()) {
    VLOG(1) << "Server migration completed";
    resetMigrationState();
  }
}

void MigrationManagementInterface::onPoolMigrationAddressAckReceived(
    ConnectionId serverConnectionId, PoolMigrationAddressFrame frame) noexcept {
  VLOG(1) << fmt::format(
      "POOL_MIGRATION_ADDRESS frame carrying address={} acknowledged on "
      "transport={}",
      quicIPAddressToString(frame.address),
      serverConnectionId.hex());
}

void MigrationManagementInterface::onServerMigrationAckReceived(
    ConnectionId serverConnectionId, ServerMigrationFrame frame) noexcept {
  VLOG(1) << fmt::format(
      "SERVER_MIGRATION frame carrying address={} acknowledged on transport={}",
      quicIPAddressToString(frame.address),
      serverConnectionId.hex());
}

void MigrationManagementInterface::onServerMigratedAckReceived(
    ConnectionId serverConnectionId) noexcept {
  VLOG(1) << "SERVER_MIGRATED frame acknowledged on transport="
          << serverConnectionId.hex();
}

void MigrationManagementInterface::errMessage(const cmsghdr &cmsg) noexcept {
}

void MigrationManagementInterface::errMessageError(
    const folly::AsyncSocketException &ex) noexcept {
  LOG(ERROR) << "Error while reading from the socket error stream: "
             << ex.what();
}

void MigrationManagementInterface::onReadError(
    const folly::AsyncSocketException &ex) noexcept {
  LOG(ERROR) << "Error while reading from the socket: " << ex.what();
}

void MigrationManagementInterface::onReadClosed() noexcept {
  LOG(INFO) << "Read socket closed";
}

void MigrationManagementInterface::getReadBuffer(void **buf,
                                                 size_t *len) noexcept {
  readBuffer_ = folly::IOBuf::create(kDefaultUDPReadBufferSize);
  *buf = readBuffer_->writableData();
  *len = kDefaultUDPReadBufferSize;
}

MigrationManagementInterface::Command
MigrationManagementInterface::parseCommandFromReadBuffer(const size_t &len) {
  auto data = std::move(readBuffer_);
  data->append(len);
  auto jsonCommand = data.get()->moveToFbString().toStdString();
  VLOG(1) << "Received command " << jsonCommand;
  return managementCommandFromJsonString(jsonCommand);
}

void MigrationManagementInterface::handleOnImminentServerMigrationCommand(
    const folly::SocketAddress &client,
    const MigrationManagementInterface::Command &command) {
  if (!migrationInProgress_) {
    migrationNotificationReceptionTime_ = std::chrono::steady_clock::now();
    migrationInProgress_ = true;
    if (command.protocol == ServerMigrationProtocol::EXPLICIT) {
      QuicIPAddress migrationAddress(command.address.value());
      quicServer_->onImminentServerMigration(command.protocol.value(),
                                             migrationAddress);
    } else {
      quicServer_->onImminentServerMigration(command.protocol.value(),
                                             folly::none);
    }

    // Handle the case in which no transports are migrated, so no calls
    // to onServerMigrationFailed() or onServerMigrationReady() happen.
    std::lock_guard<std::mutex> guard(migrationMutex_);
    if (transports_.empty() && !transportsReady_) {
      VLOG(1) << "Server ready for migration";
      transportsReady_ = true;
    }
  }
  socket_->write(client, folly::IOBuf::copyBuffer("OK"));
}

void MigrationManagementInterface::handleOnNetworkSwitchCommand(
    const folly::SocketAddress &client) {
  if (!migrationInProgress_) {
    throw std::invalid_argument("server migration is not in progress");
  }
  if (!networkSwitched_) {
    networkSwitched_ = true;
    quicServer_->onNetworkSwitch();

    // Handle the case in which no transports where migrated, so no calls to
    // onServerMigrationCompleted() happen. Note that checking only if
    // transports_ is empty is not correct, because new handshakes are not
    // blocked anymore after calling onNetworkSwitch(), meaning that a call
    // to onHandshakeFinished() could happen before taking the ownership
    // of the mutex.
    std::lock_guard<std::mutex> guard(migrationMutex_);
    if (numberOfTransportsMigrated_ == transports_.size()) {
      // This is done to update the state i
      VLOG(1) << "Server migration completed";
      resetMigrationState();
    }
  }
  socket_->write(client, folly::IOBuf::copyBuffer("OK"));
}

void MigrationManagementInterface::handleShutdownCommand(
    const folly::SocketAddress &client) {
  socket_->write(client, folly::IOBuf::copyBuffer("OK"));
  evb_->terminateLoopSoon();
}

void MigrationManagementInterface::onDataAvailable(
    const folly::SocketAddress &client,
    size_t len,
    bool truncated,
    folly::AsyncUDPSocket::ReadCallback::OnDataAvailableParams
        params) noexcept {
  // Note: if the same command is received multiple times (for example, due to a
  // retransmission), a response to the peer is sent, but the action is ignored.
  VLOG(1) << "Received management packet from client=" << client.describe();
  try {
    auto command = parseCommandFromReadBuffer(len);
    switch (command.action) {
      case Action::ON_IMMINENT_SERVER_MIGRATION:
        handleOnImminentServerMigrationCommand(client, command);
        return;
      case Action::ON_NETWORK_SWITCH:
        handleOnNetworkSwitchCommand(client);
        return;
      case Action::SHUTDOWN:
        handleShutdownCommand(client);
        return;
    }
    folly::assume_unreachable();
  } catch (const std::exception &exception) {
    LOG(ERROR) << "Ignoring command: " << exception.what();
    auto response = std::string("Bad request. Error: ") + exception.what();
    socket_->write(client, folly::IOBuf::copyBuffer(response));
  }
}

void MigrationManagementInterface::dumpMigrationNotificationTimeToFile() {
  folly::dynamic dynamic = folly::dynamic::object();
  if (migrationReadyTime_ && migrationNotificationReceptionTime_) {
    auto migrationNotificationTime =
        std::chrono::duration_cast<std::chrono::microseconds>(
            migrationReadyTime_.value() -
            migrationNotificationReceptionTime_.value())
            .count();
    dynamic["migrationNotificationTime"] = migrationNotificationTime;
  } else {
    dynamic["migrationNotificationTime"] = nullptr;
  }
  auto dynamicJson = folly::toJson(dynamic);
  auto success =
      folly::writeFile(dynamicJson, migrationNotificationTimeFile_.data());
  if (!success) {
    LOG(ERROR) << "Impossible to dump the migration notification time to file";
  }
}

} // namespace quic::samples::servermigration
