#include <folly/FileUtil.h>
#include <proxygen/httpserver/samples/server-migration/app/client/ExperimentManager.h>
#include <proxygen/httpserver/samples/server-migration/app/common/Utils.h>
#include <proxygen/httpserver/samples/server-migration/app/server/MigrationManagementInterface.h>

namespace quic::samples::servermigration {

ExperimentManager::ExperimentManager(const folly::dynamic &config,
                                     folly::EventBase *evb)
    : experimentId_(
          static_cast<ExperimentId>(config["experiment"]["id"].asInt())),
      notifyImminentMigrationAfterRequest_(
          config["experiment"]["notifyImminentMigrationAfterRequest"].asInt()),
      triggerMigrationAfterRequest_(
          config["experiment"]["triggerMigrationAfterRequest"].asInt()),
      shutdownAfterRequest_(
          config["experiment"]["shutdownAfterRequest"].asInt()),
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

void ExperimentManager::
    handleFirstAndSecondExperimentNotifyImminentServerMigration() {
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

void ExperimentManager::handleFirstAndSecondExperimentTriggerServerMigration() {
  // Drain the connection before triggering the server migration, so that all
  // the control stream frames are acknowledged by the time the server migrates.
  // Without this drain period, a PTO related to control stream frames could
  // be triggered by the client before the next request, altering the
  // measurement of the service times.
  VLOG(1) << fmt::format(
      "Draining connection for {} seconds before triggering server migration",
      drainPeriod_.count());
  std::this_thread::sleep_for(drainPeriod_);

  VLOG(1) << fmt::format("Sending command={} to migration script={}",
                         migrateCommand_,
                         containerMigrationScriptAddress_.describe());
  responseBaton_.reset();
  socket_->write(containerMigrationScriptAddress_,
                 folly::IOBuf::copyBuffer(migrateCommand_));
  waitForResponseOrRetransmit(containerMigrationScriptAddress_,
                              migrateCommand_);
}

void ExperimentManager::handleFirstAndSecondExperimentStopExperiment() {
  MigrationManagementInterface::Command command;
  command.action = MigrationManagementInterface::Action::SHUTDOWN;
  auto jsonCommand = managementCommandToJsonString(command);

  // Send the command both to the server application
  // and the container migration script.
  VLOG(1) << fmt::format("Sending command={} to server management={}",
                         jsonCommand,
                         serverManagementAddress_.describe());
  responseBaton_.reset();
  socket_->write(serverManagementAddress_,
                 folly::IOBuf::copyBuffer(jsonCommand));
  waitForResponseOrRetransmit(serverManagementAddress_, jsonCommand);

  VLOG(1) << fmt::format("Sending command={} to migration script={}",
                         jsonCommand,
                         containerMigrationScriptAddress_.describe());
  responseBaton_.reset();
  socket_->write(containerMigrationScriptAddress_,
                 folly::IOBuf::copyBuffer(jsonCommand));
  waitForResponseOrRetransmit(containerMigrationScriptAddress_, jsonCommand);
}

void ExperimentManager::maybeNotifyImminentServerMigration(
    const int64_t &numberOfCompletedRequests) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
    case ExperimentId::SECOND:
      if (numberOfCompletedRequests == notifyImminentMigrationAfterRequest_) {
        handleFirstAndSecondExperimentNotifyImminentServerMigration();
      }
      return;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

bool ExperimentManager::maybeTriggerServerMigration(
    const int64_t &numberOfCompletedRequests) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
    case ExperimentId::SECOND:
      if (numberOfCompletedRequests == triggerMigrationAfterRequest_) {
        handleFirstAndSecondExperimentTriggerServerMigration();
        return proactiveExplicit_;
      }
      return false;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

bool ExperimentManager::maybeStopExperiment(
    const int64_t &numberOfCompletedRequests) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
    case ExperimentId::SECOND:
      if (numberOfCompletedRequests == shutdownAfterRequest_) {
        handleFirstAndSecondExperimentStopExperiment();
        return true;
      }
      return false;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

void ExperimentManager::maybeSaveServiceTime(
    const int64_t &requestNumber,
    const long &serviceTime,
    const folly::SocketAddress &serverAddress) {
  switch (experimentId_) {
    case ExperimentId::FIRST:
      if (requestNumber == triggerMigrationAfterRequest_ + 1) {
        serviceTimes_.push_back(serviceTime);
        serverAddresses_.push_back(serverAddress.describe());
      }
      return;
    case ExperimentId::SECOND:
      CHECK_GT(triggerMigrationAfterRequest_, 1);
      if (requestNumber == 1) {
        secondExperimentOriginalServerAddress_ = serverAddress;
        return;
      }
      if (requestNumber > triggerMigrationAfterRequest_ &&
          !firstResponseFromNewServerAddressReceived_) {
        if (secondExperimentOriginalServerAddress_ != serverAddress) {
          firstResponseFromNewServerAddressReceived_ = true;
        }
        serviceTimes_.push_back(serviceTime);
        serverAddresses_.push_back(serverAddress.describe());
      }
      return;
  }
  LOG(ERROR) << "Unknown experiment ID. Stopping the manager";
  folly::assume_unreachable();
}

void ExperimentManager::dumpServiceTimesToFile() {
  folly::dynamic serviceTimes = folly::dynamic::array();
  for (const auto &time : serviceTimes_) {
    serviceTimes.push_back(time);
  }

  folly::dynamic serverAddresses = folly::dynamic::array();
  for (const auto &address : serverAddresses_) {
    serverAddresses.push_back(address);
  }

  folly::dynamic dynamic = folly::dynamic::object();
  dynamic["experiment"] = static_cast<int64_t>(experimentId_);
  dynamic["serviceTimes"] = serviceTimes;
  dynamic["serverAddresses"] = serverAddresses;

  auto dynamicJson = folly::toJson(dynamic);
  auto success = folly::writeFile(dynamicJson, serviceTimesFile_.data());
  if (!success) {
    LOG(ERROR) << "Impossible to dump the service times to file";
  }
}

void ExperimentManager::updateServerManagementAddress(
    const folly::IPAddress &newServerAddress) {
  folly::SocketAddress newManagementAddress = folly::SocketAddress(
      newServerAddress, serverManagementAddress_.getPort());
  VLOG(1) << fmt::format("Updating the server management address from {} to {}",
                         serverManagementAddress_.describe(),
                         newManagementAddress.describe());
  serverManagementAddress_ = std::move(newManagementAddress);
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
