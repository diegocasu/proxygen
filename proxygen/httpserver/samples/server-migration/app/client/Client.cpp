#include <fizz/protocol/ZlibCertificateDecompressor.h>
#include <fizz/protocol/ZstdCertificateDecompressor.h>
#include <proxygen/httpserver/samples/server-migration/app/client/Client.h>
#include <proxygen/httpserver/samples/server-migration/app/client/DummyCertificateVerifier.h>
#include <proxygen/httpserver/samples/server-migration/app/client/RandomPoolMigrationAddressScheduler.h>
#include <proxygen/httpserver/samples/server-migration/app/common/FizzData.h>
#include <proxygen/httpserver/samples/server-migration/app/common/Utils.h>
#include <proxygen/lib/http/session/HQSession.h>

namespace quic::samples::servermigration {

void Client::generateSeeds() {
  std::array<uint32_t, 3> seedBuffer;
  seedSequence_.generate(seedBuffer.begin(), seedBuffer.end());
  seeds_.poaScheduler = seedBuffer[0];
  seeds_.requestType = seedBuffer[1];
  seeds_.postBodyDimension = seedBuffer[2];
  VLOG(1) << fmt::format(
      "Generated seeds PoA scheduler={}, request type={}, POST body={} "
      "from master seed={}",
      seeds_.poaScheduler,
      seeds_.requestType,
      seeds_.postBodyDimension,
      seeds_.master);
}

void Client::initializeRequestScheduler(const folly::dynamic& config) {
  folly::Optional<RequestScheduler::Pattern> pattern;
  folly::Optional<RequestScheduler::Body> body;
  auto requestPatternConfig = config["requestPattern"];
  auto requestBodyConfig = config["requestBody"];

  if (requestPatternConfig["sporadic"].asBool()) {
    pattern = RequestScheduler::Pattern::SPORADIC;
  } else if (requestPatternConfig["backToBack"].asBool()) {
    pattern = RequestScheduler::Pattern::BACK_TO_BACK;
  } else {
    throw std::invalid_argument(
        "Invalid \"requestPattern\": it must be either \"sporadic\" or "
        "\"backToBack\"");
  }

  if (requestBodyConfig["fixed"].asBool()) {
    body = RequestScheduler::Body::FIXED;
  } else if (requestBodyConfig["fromDistribution"].asBool()) {
    body = RequestScheduler::Body::FROM_DISTRIBUTION;
  } else {
    throw std::invalid_argument(
        "Invalid \"requestBody\": it must be either \"fixed\" or "
        "\"fromDistribution\"");
  }
  requestScheduler_ =
      std::make_unique<RequestScheduler>(pattern.value(),
                                         body.value(),
                                         seeds_.requestType,
                                         seeds_.postBodyDimension);
}

std::shared_ptr<fizz::client::FizzClientContext> Client::createFizzContext() {
  auto context = std::make_shared<fizz::client::FizzClientContext>();
  auto certificate =
      fizz::CertUtils::makeSelfCert(kDefaultCertificateData, kDefaultKeyData);
  context->setClientCertificate(std::move(certificate));

  std::vector<std::string> supportedAlpns{proxygen::kH3,
                                          proxygen::kHQ,
                                          proxygen::kH3FBCurrentDraft,
                                          proxygen::kH3CurrentDraft,
                                          proxygen::kHQCurrentDraft};
  context->setSupportedAlpns(supportedAlpns);
  context->setDefaultShares(
      {fizz::NamedGroup::x25519, fizz::NamedGroup::secp256r1});

  auto manager = std::make_shared<fizz::CertDecompressionManager>();
  manager->setDecompressors(
      {std::make_shared<fizz::ZstdCertificateDecompressor>(),
       std::make_shared<fizz::ZlibCertificateDecompressor>()});
  context->setCertDecompressionManager(std::move(manager));

  return context;
}

std::shared_ptr<FizzClientQuicHandshakeContext>
Client::createFizzHandshakeContext(const folly::dynamic& config) {
  std::shared_ptr<FizzClientQuicHandshakeContext> context;

  if (config["keyLogging"]["enable"].asBool()) {
    QuicKeyLogWriter::Config keyLogWriterConfig;
    keyLogWriterConfig.fileName = config["keyLogging"]["file"].asString();
    keyLogWriterConfig.flushPolicy = QuicKeyLogWriter::FlushPolicy::IMMEDIATELY;
    keyLogWriterConfig.writeMode = QuicKeyLogWriter::WriteMode::OVERWRITE;

    context = FizzClientQuicHandshakeContext::Builder()
                  .setFizzClientContext(createFizzContext())
                  .setCertificateVerifier(
                      std::make_unique<DummyCertificateVerifier>())
                  .enableKeyLogging(keyLogWriterConfig)
                  .build();
    VLOG(1) << fmt::format(
        "Key logging enabled, with file={}, flush policy=immediately, write "
        "mode=overwrite",
        keyLogWriterConfig.fileName);
  } else {
    context = FizzClientQuicHandshakeContext::Builder()
                  .setFizzClientContext(createFizzContext())
                  .setCertificateVerifier(
                      std::make_unique<DummyCertificateVerifier>())
                  .build();
    VLOG(1) << "Key logging disabled";
  }

  return context;
}

void Client::initializeServerMigrationSettings(const folly::dynamic& config) {
  auto serverMigrationConfig = config["serverMigration"];
  std::unordered_set<ServerMigrationProtocol> migrationProtocols;

  if (!serverMigrationConfig["enable"].asBool()) {
    VLOG(1) << "Server migration disabled";
    return;
  }
  if (serverMigrationConfig["explicit"].asBool()) {
    migrationProtocols.insert(ServerMigrationProtocol::EXPLICIT);
  }
  if (serverMigrationConfig["poolOfAddresses"].asBool()) {
    migrationProtocols.insert(ServerMigrationProtocol::POOL_OF_ADDRESSES);
  }
  if (serverMigrationConfig["symmetric"].asBool()) {
    migrationProtocols.insert(ServerMigrationProtocol::SYMMETRIC);
  }
  if (serverMigrationConfig["synchronizedSymmetric"].asBool()) {
    migrationProtocols.insert(ServerMigrationProtocol::SYNCHRONIZED_SYMMETRIC);
  }

  if (migrationProtocols.empty()) {
    LOG(ERROR) << "Impossible to enable server migration: "
                  "all the protocols are disabled";
    return;
  }

  VLOG(1) << "Server migration enabled with protocols="
          << migrationProtocolsToString(migrationProtocols);
  quicClient_->allowServerMigration(migrationProtocols);
  quicClient_->setPoolMigrationAddressSchedulerFactory(
      std::make_unique<RandomPoolMigrationAddressSchedulerFactory>(
          seeds_.poaScheduler));
  // setServerMigrationEventCallback() is not done here, but
  // in start(), because shared_from_this() cannot be called
  // while constructing the object.
}

void Client::initializeTransportSettings() {
  // Use the default settings of mvfst, except for the ones that
  // prevent server/client migration or limit the experiments.
  // By default, the congestion controller is Cubic and the idle
  // timeout is 60 seconds.
  TransportSettings settings;

  // Set the number of advertised streams to the
  // maximum allowed by the standard.
  settings.advertisedInitialMaxStreamsBidi = kMaxMaxStreams;
  settings.advertisedInitialMaxStreamsUni = kMaxMaxStreams;

  // Do not close the connection if multiple PTOs occur.
  // Use only the idle timeout to detect inactivity.
  settings.maxNumPTOs = 100;

  // Set the number of Connection IDs generated by the server that the client
  // is willing to store. This number determines how many NEW_CONNECTION_ID
  // frames will be sent by the server at the end of the handshake (CIDs are
  // sent all together in bulk). At each client migration, upon the reception
  // of a PATH_CHALLENGE, the client retires the current CID used to identify
  // the server and expects another one to be available, otherwise the
  // connection is closed. Therefore, this number must be chosen depending on
  // the expected maximum number of client migrations.
  // Note that, in the transport code, the actual number is chosen as the
  // minimum between selfActiveConnectionIdLimit and
  // kDefaultActiveConnectionIdLimit, where the latter is equal to 100.
  // Therefore, if more than 100 migrations are needed,
  // kDefaultActiveConnectionIdLimit must be modified.
  settings.selfActiveConnectionIdLimit = 30;

  quicClient_->setTransportSettings(settings);
}

Client::Client(const folly::dynamic& config)
    : serverHost_(config["serverHost"].asString()),
      serverPort_(config["serverPort"].asInt()),
      networkThread_("networkThread"),
      seedSequence_({config["seed"].asInt()}) {
  seeds_.master = config["seed"].asInt();
  generateSeeds();

  initializeRequestScheduler(config);
  curl_ = std::make_unique<Curl>();

  auto evb = networkThread_.getEventBase();
  experimentManager_ = std::make_unique<ExperimentManager>(config, evb);

  evb->runInEventBaseThreadAndWait([&] {
    auto socket = std::make_unique<folly::AsyncUDPSocket>(evb);
    quicClient_ = std::make_shared<QuicClientTransport>(
        evb,
        std::move(socket),
        createFizzHandshakeContext(config),
        kDefaultConnectionIdSize);

    initializeServerMigrationSettings(config);
    initializeTransportSettings();

    folly::SocketAddress serverAddress(serverHost_, serverPort_, true);
    quicClient_->addNewPeerAddress(serverAddress);
    quicClient_->setHostname(serverHost_);

    std::vector<QuicVersion> supportedVersions{{QuicVersion::MVFST,
                                                QuicVersion::MVFST_EXPERIMENTAL,
                                                QuicVersion::MVFST_ALIAS,
                                                QuicVersion::QUIC_V1,
                                                QuicVersion::QUIC_DRAFT}};
    quicClient_->setSupportedVersions(supportedVersions);

    wangle::TransportInfo transportInfo;
    session_ = new proxygen::HQUpstreamSession(transactionsTimeout_,
                                               connectionTimeout_,
                                               nullptr,
                                               transportInfo,
                                               nullptr);
    session_->setForceUpstream1_1(false);
    session_->setSocket(quicClient_);
    session_->setConnectCallback(this);
  });
}

void Client::start() {
  LOG(INFO) << fmt::format("Connecting to {}:{}", serverHost_, serverPort_);
  quicClient_->setServerMigrationEventCallback(shared_from_this());
  auto evb = networkThread_.getEventBase();

  evb->runInEventBaseThreadAndWait([&] {
    experimentManager_->start();
    session_->startNow();
    quicClient_->start(session_, session_);
  });

  startDone_.wait();
  if (connectionFailed_) {
    return;
  }
  scheduleRequests();
}

void Client::onReplaySafe() {
  startDone_.post();
}

void Client::connectError(quic::QuicError error) {
  LOG(ERROR) << fmt::format("Failed to connect, error={}, msg={}",
                            toString(error.code),
                            error.message);
  connectionFailed_ = true;
  startDone_.post();
}

void Client::scheduleRequests() {
  LOG(INFO) << "Starting scheduling of requests";
  auto evb = networkThread_.getEventBase();
  uint64_t numberOfOpenableStreams =
      quicClient_->getNumOpenableBidirectionalStreams();
  uint64_t numberOfCompletedRequests = 0;
  bool triggerPTO = false;

  while (numberOfOpenableStreams > 0) {
    VLOG(1) << "Current number of openable streams=" << numberOfOpenableStreams;
    VLOG(1) << "Completed requests=" << numberOfCompletedRequests;
    std::chrono::time_point<std::chrono::steady_clock> startRequestTime;

    // This method blocks for the required amount of time
    // if the request pattern is sporadic.
    auto request = requestScheduler_->nextRequest();

    evb->runInEventBaseThreadAndWait([&] {
      auto transaction = session_->newTransaction(curl_.get());
      if (!transaction) {
        LOG(ERROR) << "Impossible to create a new transaction. "
                      "Stopping the client";
        session_->drain();
        session_->closeWhenIdle();
        return;
      }
      startRequestTime = std::chrono::steady_clock::now();
      curl_->sendRequest(transaction,
                         request.httpMethod,
                         request.url,
                         std::move(request.body));
      if (triggerPTO) {
        VLOG(1) << "Artificially triggering the PTO callback to support "
                   "the Proactive Explicit protocol";
        quicClient_->onProbeTimeout();
      }
    });

    auto gotResponse = curl_->waitForResponse(transactionsTimeout_);
    auto endRequestTime = std::chrono::steady_clock::now();
    auto serviceTime = std::chrono::duration_cast<std::chrono::microseconds>(
                           endRequestTime - startRequestTime)
                           .count();
    triggerPTO = false;

    if (!gotResponse) {
      LOG(ERROR) << "Connection timeout while waiting for the response. "
                    "Stopping the client";
      break;
    }

    auto responseHeaders = curl_->getResponseHeaders();
    auto responseBody = curl_->getResponseBody();
    if (responseHeaders) {
      VLOG(1) << "Received response headers" << *responseHeaders;
    } else {
      VLOG(1) << "Received empty response headers";
    }
    if (responseBody) {
      VLOG(1) << fmt::format("Received response body of size={} bytes",
                             responseBody->length());
    } else {
      VLOG(1) << "Received empty body";
    }

    ++numberOfCompletedRequests;
    --numberOfOpenableStreams;

    experimentManager_->maybeNotifyImminentServerMigration(
        numberOfCompletedRequests);
    experimentManager_->maybeSaveServiceTime(numberOfCompletedRequests,
                                             serviceTime);
    triggerPTO = experimentManager_->maybeTriggerServerMigration(
        numberOfCompletedRequests);
    maybeUpdateServerManagementAddress();
    auto stop =
        experimentManager_->maybeStopExperiment(numberOfCompletedRequests);
    if (stop) {
      experimentManager_->dumpServiceTimesToFile();
      break;
    }
  }
  LOG(INFO) << "Stopping the client";
}

void Client::onPoolMigrationAddressReceived(
    PoolMigrationAddressFrame frame) noexcept {
  VLOG(1) << "Received POOL_MIGRATION_ADDRESS frame containing address "
          << quicIPAddressToString(frame.address);
}

void Client::onServerMigrationReceived(ServerMigrationFrame frame) noexcept {
  VLOG(1) << "Received SERVER_MIGRATION frame containing address "
          << quicIPAddressToString(frame.address);
}

void Client::onServerMigratedReceived() noexcept {
  VLOG(1) << "Received SERVER_MIGRATED frame";
}

void Client::onServerMigrationProbingStarted(
    ServerMigrationProtocol protocol, folly::SocketAddress address) noexcept {
  VLOG(1) << fmt::format(
      "Started server migration probing for protocol={}, involving address={}",
      serverMigrationProtocolToString(protocol),
      address.describe());
}

void Client::onServerMigrationCompleted() noexcept {
  VLOG(1) << "Server migration completed";
  std::lock_guard<std::mutex> guard(serverMigrationCompletedMutex_);
  newServerAddress_ = quicClient_->getPeerAddress().getIPAddress();
}

bool Client::maybeUpdateServerManagementAddress() {
  std::lock_guard<std::mutex> guard(serverMigrationCompletedMutex_);
  if (!newServerAddress_) {
    return false;
  }

  experimentManager_->updateServerManagementAddress(newServerAddress_.value());
  newServerAddress_.clear();
  return true;
}

} // namespace quic::samples::servermigration
