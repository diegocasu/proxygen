#include <proxygen/httpserver/samples/server-migration/app/client/ExperimentManager.h>
#include <proxygen/httpserver/samples/server-migration/app/common/Utils.h>
#include <proxygen/httpserver/samples/server-migration/app/server/MigrationManagementInterface.h>

namespace quic::samples::servermigration {

ExperimentManager::ExperimentManager(const folly::dynamic &config,
                                     folly::EventBase *evb)
    : experimentId_(
          static_cast<ExperimentId>(config["experiment"]["id"].asInt())),
      serverManagementAddress_(
          config["serverHost"].asString(),
          config["experiment"]["serverManagementPort"].asInt(),
          true),
      containerMigrationScriptAddress_(
          config["experiment"]["containerMigrationScriptHost"].asString(),
          config["experiment"]["containerMigrationScriptPort"].asInt(),
          true) {
  if (config["experiment"]["id"].asInt() >
      static_cast<int64_t>(ExperimentId::MAX)) {
    throw std::invalid_argument("Bad experiment ID");
  }

  auto protocolField =
      config["experiment"]["serverMigrationProtocol"].asString();
  if (protocolField == "proactiveExplicit") {
    proactiveExplicit_ = true;
  }
  if (protocolField == "proactiveExplicit" ||
      protocolField == "reactiveExplicit") {
    migrationProtocol_ = ServerMigrationProtocol::EXPLICIT;
    migrationAddress_ = folly::SocketAddress(
        config["experiment"]["serverMigrationHost"].asString(),
        config["experiment"]["serverMigrationPort"].asInt(),
        true);
  } else if (protocolField == "poolOfAddresses") {
    migrationProtocol_ = ServerMigrationProtocol::POOL_OF_ADDRESSES;
  } else if (protocolField == "symmetric") {
    migrationProtocol_ = ServerMigrationProtocol::SYMMETRIC;
  } else if (protocolField == "synchronizedSymmetric") {
    migrationProtocol_ = ServerMigrationProtocol::SYNCHRONIZED_SYMMETRIC;
  } else {
    throw std::invalid_argument("Bad protocol");
  }

  socket_ = std::make_unique<folly::AsyncUDPSocket>(evb);
  if (serverManagementAddress_.getFamily() == AF_INET) {
    socket_->bind(folly::SocketAddress("0.0.0.0", 0));
  } else {
    socket_->bind(folly::SocketAddress("::", 0));
  }
  socket_->setErrMessageCallback(this);

  auto migrationAddressString =
      migrationAddress_.has_value() ? migrationAddress_->describe() : "none";
  VLOG(1) << fmt::format(
      "Initialized experiment manager with experiment ID={}, "
      "server management address={}, container migration script address={}, "
      "server migration protocol={}, migration address={}",
      static_cast<int64_t>(experimentId_),
      serverManagementAddress_.describe(),
      containerMigrationScriptAddress_.describe(),
      serverMigrationProtocolToString(migrationProtocol_),
      migrationAddressString);
}

void ExperimentManager::start() {
  LOG(INFO) << "Starting experiment manager on "
            << socket_->address().describe();
  socket_->resumeRead(this);
}

void ExperimentManager::waitForResponseOrRetransmit(
    const folly::SocketAddress &destination, const std::string &command) {
  // Wait for response, or retransmit. Note that the socket runs
  // on an event base of a different thread.
  unsigned int numberOfRetransmissions = 0;
  while (true) {
    auto gotResponse = responseBaton_.try_wait_for(responseTimeout_);
    if (gotResponse) {
      break;
    }
    if (numberOfRetransmissions == maxNumberOfRetransmissions_) {
      LOG(ERROR) << "Reached max number of retransmissions";
      break;
    }
    ++numberOfRetransmissions;
    responseBaton_.reset();
    socket_->write(destination, folly::IOBuf::copyBuffer(command));
    VLOG(1) << fmt::format("Command response timeout. Retransmission {}/{}",
                           numberOfRetransmissions,
                           maxNumberOfRetransmissions_);
  }
}

void ExperimentManager::handleFirstExperimentNotifyImminentServerMigration() {
  MigrationManagementInterface::Command command;
  command.action =
      MigrationManagementInterface::Action::ON_IMMINENT_SERVER_MIGRATION;
  command.protocol = migrationProtocol_;
  if (migrationAddress_) {
    command.address = migrationAddress_.value();
  }

  auto jsonCommand = managementCommandToJsonString(command);
  VLOG(1) << fmt::format("Sending command={} to server management={}",
                         jsonCommand,
                         serverManagementAddress_.describe());
  responseBaton_.reset();
  socket_->write(serverManagementAddress_,
                 folly::IOBuf::copyBuffer(jsonCommand));
  waitForResponseOrRetransmit(serverManagementAddress_, jsonCommand);
}

void ExperimentManager::handleFirstExperimentTriggerServerMigration() {
  // TODO implement when migration script is ready
}

void ExperimentManager::handleFirstExperimentStopExperiment() {
  MigrationManagementInterface::Command command;
  command.action = MigrationManagementInterface::Action::SHUTDOWN;
  auto jsonCommand = managementCommandToJsonString(command);
  VLOG(1) << fmt::format("Sending command={} to server management={}",
                         jsonCommand,
                         serverManagementAddress_.describe());
  responseBaton_.reset();
  socket_->write(serverManagementAddress_,
                 folly::IOBuf::copyBuffer(jsonCommand));
  waitForResponseOrRetransmit(serverManagementAddress_, jsonCommand);
}

void ExperimentManager::maybeNotifyImminentServerMigration(
    const uint64_t &numberOfCompletedRequests) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
      if (numberOfCompletedRequests == 1) {
        handleFirstExperimentNotifyImminentServerMigration();
      }
      return;
    case ExperimentId::SECOND:
      // TODO
      return;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

bool ExperimentManager::maybeTriggerServerMigration(
    const uint64_t &numberOfCompletedRequests) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
      if (numberOfCompletedRequests == 2) {
        handleFirstExperimentTriggerServerMigration();
      }
      return proactiveExplicit_;
    case ExperimentId::SECOND:
      // TODO
      return proactiveExplicit_;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

bool ExperimentManager::maybeStopExperiment(
    const uint64_t &numberOfCompletedRequests) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
      if (numberOfCompletedRequests == 3) {
        handleFirstExperimentStopExperiment();
        return true;
      }
      return false;
    case ExperimentId::SECOND:
      // TODO
      return false;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

void ExperimentManager::errMessage(const cmsghdr &cmsg) noexcept {
}

void ExperimentManager::errMessageError(
    const folly::AsyncSocketException &ex) noexcept {
  LOG(ERROR) << "Error while reading from the socket error stream: "
             << ex.what();
}

void ExperimentManager::onReadError(
    const folly::AsyncSocketException &ex) noexcept {
  LOG(ERROR) << "Error while reading from the socket: " << ex.what();
}

void ExperimentManager::onReadClosed() noexcept {
  LOG(INFO) << "Read socket closed";
}

void ExperimentManager::getReadBuffer(void **buf, size_t *len) noexcept {
  readBuffer_ = folly::IOBuf::create(kDefaultUDPReadBufferSize);
  *buf = readBuffer_->writableData();
  *len = kDefaultUDPReadBufferSize;
}

void ExperimentManager::onDataAvailable(
    const folly::SocketAddress &client,
    size_t len,
    bool truncated,
    folly::AsyncUDPSocket::ReadCallback::OnDataAvailableParams
        params) noexcept {
  VLOG(1) << "Received packet from " << client.describe();

  if (client != serverManagementAddress_ &&
      client != containerMigrationScriptAddress_) {
    VLOG(1) << "Discarding packet from unknown host";
    return;
  }

  auto data = std::move(readBuffer_);
  data->append(len);
  auto resultString = data.get()->moveToFbString().toStdString();
  VLOG(1) << "Received response " << resultString;
  responseBaton_.post();
}

} // namespace quic::samples::servermigration
