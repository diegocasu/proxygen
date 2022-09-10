#include <folly/FileUtil.h>
#include <folly/String.h>
#include <folly/json.h>
#include <proxygen/httpserver/samples/servermigration/app/client/HandoverManager.h>
#include <quic/QuicConstants.h>

namespace quic::samples::servermigration {

HandoverManager::HandoverManager(
    folly::EventBase *transportEvb,
    std::shared_ptr<QuicClientTransport> quicClient)
    : transportEvb_(transportEvb), quicClient_(std::move(quicClient)) {
  auto evb = managerThread_.getEventBase();
  socket_ = std::make_unique<folly::AsyncUDPSocket>(evb);
  folly::SocketAddress address("0.0.0.0", 5555);
  socket_->bind(address);
  socket_->setErrMessageCallback(this);
}

void HandoverManager::start() {
  LOG(INFO) << "Starting handover manager on: "
            << socket_->address().describe();
  socket_->resumeRead(this);
}

void HandoverManager::errMessage(const cmsghdr &cmsg) noexcept {
}

void HandoverManager::errMessageError(
    const folly::AsyncSocketException &ex) noexcept {
  LOG(ERROR) << "Error while reading from the socket error stream: "
             << ex.what();
}

void HandoverManager::onReadError(
    const folly::AsyncSocketException &ex) noexcept {
  LOG(ERROR) << "Error while reading from the socket: " << ex.what();
}

void HandoverManager::onReadClosed() noexcept {
  LOG(INFO) << "Read socket closed";
}

void HandoverManager::getReadBuffer(void **buf, size_t *len) noexcept {
  readBuffer_ = folly::IOBuf::create(kDefaultUDPReadBufferSize);
  *buf = readBuffer_->writableData();
  *len = kDefaultUDPReadBufferSize;
}

void HandoverManager::onDataAvailable(
    const folly::SocketAddress &client,
    size_t len,
    bool truncated,
    folly::AsyncUDPSocket::ReadCallback::OnDataAvailableParams
        params) noexcept {
  VLOG(1) << "Received handover management packet from " << client.describe();
  auto data = std::move(readBuffer_);
  data->append(len);
  auto command = data.get()->moveToFbString().toStdString();
  VLOG(1) << "Received command " << command;

  try {
    auto dynamic = folly::parseJson(command);
    auto actionField = dynamic["action"].asString();
    if (actionField == "handover") {
      folly::SocketAddress newAddress;
      newAddress.setFromLocalIpPort(dynamic["address"].asString());

      auto accessPoint = dynamic["accessPoint"].asString();
      auto accessPointRouter = dynamic["accessPointRouter"].asString();
      auto otherAccessPointSubnet =
          dynamic["otherAccessPointSubnet"].asString();

      doHandover(
          newAddress, accessPoint, accessPointRouter, otherAccessPointSubnet);
    }
  } catch (const std::exception &exception) {
    LOG(ERROR) << "Ignoring command: " << exception.what();
    auto response = std::string("Bad request. Error: ") + exception.what();
    socket_->write(client, folly::IOBuf::copyBuffer(response));
  }
}

bool HandoverManager::searchInOutputFile(const std::string &fileName,
                                         const std::string &str) {
  std::string fileContent;
  folly::readFile(fileName.data(), fileContent);
  folly::toLowerAscii(fileContent);

  auto found = fileContent.find(str);
  return found != std::string::npos;
}

void HandoverManager::doHandover(const folly::SocketAddress &newAddress,
                                 const std::string &accessPoint,
                                 const std::string &accessPointRouter,
                                 const std::string &otherAccessPointSubnet) {
  transportEvb_->runInEventBaseThreadAndWait([&] {
    std::string cmdOutputFile("cmdOutput.txt");
    std::chrono::milliseconds waitInterval(1000);
    auto maxAttempts = 10u;
    auto attempts = 0u;

    // Perform Wi-Fi handover.
    auto cmdHandover =
        fmt::format("sudo nmcli dev wifi connect {} 2>&1 | sudo tee {}",
                    accessPoint,
                    cmdOutputFile);
    while (true) {
      LOG(INFO) << fmt::format("Running command '{}'", cmdHandover);
      std::system(cmdHandover.data());
      if (searchInOutputFile(cmdOutputFile, "error")) {
        ++attempts;
        LOG(ERROR) << fmt::format(
            "Failed handover attempt {}/{}", attempts, maxAttempts);
        if (attempts >= maxAttempts) {
          LOG(ERROR) << "Handover failed";
          return;
        }
        continue;
      }
      LOG(INFO) << "Handover succeeded";
      attempts = 0;
      break;
    }

    // Add route for the other access point.
    auto cmdRoute =
        fmt::format("sudo ip route add {} via {} 2>&1 | sudo tee {}",
                    otherAccessPointSubnet,
                    accessPointRouter,
                    cmdOutputFile);
    while (true) {
      LOG(INFO) << fmt::format("Running command '{}'", cmdRoute);
      std::system(cmdRoute.data());
      if (searchInOutputFile(cmdOutputFile, "error")) {
        ++attempts;
        LOG(ERROR) << fmt::format(
            "Failed routing table update {}/{}", attempts, maxAttempts);
        if (attempts >= maxAttempts) {
          LOG(ERROR) << "Routing table update failed";
          return;
        }
        continue;
      }
      LOG(INFO) << "Routing table updated";
      attempts = 0;
      break;
    }

    // Update client socket to reflect the new address.
    auto newClientSocket =
        std::make_unique<folly::AsyncUDPSocket>(transportEvb_);
    newClientSocket->bind(newAddress);
    quicClient_->onNetworkSwitch(std::move(newClientSocket));
  });
}

} // namespace quic::samples::servermigration