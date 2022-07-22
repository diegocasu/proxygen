#include <fizz/server/AeadTicketCipher.h>
#include <fizz/server/CertManager.h>
#include <fizz/server/TicketCodec.h>
#include <proxygen/httpserver/samples/servermigration/app/common/FizzData.h>
#include <proxygen/httpserver/samples/servermigration/app/common/Utils.h>
#include <proxygen/httpserver/samples/servermigration/app/server/Server.h>
#include <proxygen/httpserver/samples/servermigration/app/server/TransportFactory.h>
#include <proxygen/lib/http/session/HQDownstreamSession.h>

namespace quic::samples::servermigration {

void Server::initializeServerMigrationSettings(const folly::dynamic& config) {
  auto serverMigrationConfig = config["serverMigration"];
  if (!serverMigrationConfig["enable"].asBool()) {
    VLOG(1) << "Server migration disabled";
    return;
  }
  if (serverMigrationConfig["explicit"].asBool()) {
    migrationProtocols_.insert(ServerMigrationProtocol::EXPLICIT);
  }
  if (serverMigrationConfig["symmetric"].asBool()) {
    migrationProtocols_.insert(ServerMigrationProtocol::SYMMETRIC);
  }
  if (serverMigrationConfig["synchronizedSymmetric"].asBool()) {
    migrationProtocols_.insert(ServerMigrationProtocol::SYNCHRONIZED_SYMMETRIC);
  }
  if (serverMigrationConfig["poolOfAddresses"].asBool()) {
    auto addressPool = serverMigrationConfig["addressPool"];
    if (addressPool.empty()) {
      LOG(ERROR) << "Empty address pool for the Pool of Addresses protocol. "
                 << "The protocol will be ignored";
      return;
    }
    for (const auto& address : addressPool) {
      folly::SocketAddress socketAddress;
      socketAddress.setFromIpPort(address.asString());
      QuicIPAddress quicIpAddress(socketAddress);
      poolMigrationAddresses_.insert(quicIpAddress);
    }
    migrationProtocols_.insert(ServerMigrationProtocol::POOL_OF_ADDRESSES);
  }

  if (migrationProtocols_.empty()) {
    LOG(ERROR) << "Impossible to enable server migration: "
                  "all the protocols are disabled";
    return;
  }
  VLOG(1) << "Server migration enabled with protocols="
          << migrationProtocolsToString(migrationProtocols_);
  if (!poolMigrationAddresses_.empty()) {
    VLOG(1) << "Pool migration addresses="
            << poolMigrationAddressesToString(poolMigrationAddresses_);
  }
}

void Server::initializeTransportSettings() {
  // Use the default settings of mvfst, except for the ones that
  // prevent server/client migration or limit the experiments.
  // By default, the congestion controller is Cubic.
  TransportSettings settings;

  // Increase the idle timeout to 120 seconds.
  settings.idleTimeout = kDefaultIdleTimeout * 2;

  // Set the number of advertised streams to the
  // maximum allowed by the standard.
  settings.advertisedInitialMaxStreamsBidi = kMaxMaxStreams;
  settings.advertisedInitialMaxStreamsUni = kMaxMaxStreams;

  // Allow client migration. This setting does not involve server migration.
  // Note that the maximum number of client migrations is defined by
  // kMaxNumMigrationsAllowed and is equal to 100.
  settings.disableMigration = false;

  // Do not close the connection if multiple PTOs occur.
  // Use only the idle timeout to detect inactivity.
  settings.maxNumPTOs = 100;

  // Set the number of Connection IDs generated by the client that the server
  // is willing to store. This number determines how many NEW_CONNECTION_ID
  // frames will be sent by the client at the end of the handshake (CIDs are
  // sent all together in bulk). At each server migration, upon the reception
  // of a PATH_CHALLENGE, the server retires the current CID used to identify
  // the client and expects another one to be available, otherwise the
  // connection is closed. Therefore, this number must be chosen depending on
  // the expected maximum number of server migrations.
  // Note that, in the transport code, the actual number is chosen as the
  // minimum between selfActiveConnectionIdLimit and
  // kDefaultActiveConnectionIdLimit, where the latter is equal to 100.
  // Therefore, if more than 100 migrations are needed,
  // kDefaultActiveConnectionIdLimit must be modified.
  settings.selfActiveConnectionIdLimit = 30;

  // Enable keep alive mechanism.
  settings.enableKeepalive = true;

  quicServer_->setTransportSettings(settings);
}

void Server::initializeFizzContext() {
  auto certificateManager = std::make_shared<fizz::server::CertManager>();
  auto certificate =
      fizz::CertUtils::makeSelfCert(kDefaultCertificateData, kDefaultKeyData);
  certificateManager->addCert(std::move(certificate), true);
  auto certificate2 = fizz::CertUtils::makeSelfCert(kPrime256v1CertificateData,
                                                    kPrime256v1KeyData);
  certificateManager->addCert(std::move(certificate2), false);

  auto serverContext = std::make_shared<fizz::server::FizzServerContext>();
  serverContext->setCertManager(certificateManager);

  auto ticketCipher = std::make_shared<fizz::server::Aead128GCMTicketCipher<
      fizz::server::TicketCodec<fizz::server::CertificateStorage::X509>>>(
      serverContext->getFactoryPtr(), std::move(certificateManager));
  std::array<uint8_t, 32> ticketSeed;
  folly::Random::secureRandom(ticketSeed.data(), ticketSeed.size());
  ticketCipher->setTicketSecrets({{folly::range(ticketSeed)}});
  serverContext->setTicketCipher(ticketCipher);
  serverContext->setClientAuthMode(fizz::server::ClientAuthMode::None);

  std::vector<std::string> supportedAlpns{proxygen::kH3,
                                          proxygen::kHQ,
                                          proxygen::kH3FBCurrentDraft,
                                          proxygen::kH3CurrentDraft,
                                          proxygen::kHQCurrentDraft};
  serverContext->setSupportedAlpns(supportedAlpns);
  serverContext->setAlpnMode(fizz::server::AlpnMode::Required);

  serverContext->setSendNewSessionTicket(false);
  serverContext->setEarlyDataFbOnly(false);
  serverContext->setVersionFallbackEnabled(false);

  std::shared_ptr<fizz::server::ReplayCache> replayCache =
      std::make_shared<fizz::server::AllowAllReplayReplayCache>();
  fizz::server::ClockSkewTolerance tolerance;
  tolerance.before = std::chrono::minutes(-5);
  tolerance.after = std::chrono::minutes(5);
  serverContext->setEarlyDataSettings(true, tolerance, replayCache);

  quicServer_->setFizzContext(serverContext);
}

Server::Server(const folly::dynamic& config)
    : host_(config["host"].asString()),
      port_(config["port"].asInt()),
      numberOfWorkerThreads_(config["numberOfWorkerThreads"].asInt()),
      quicServer_(QuicServer::createQuicServer()) {
  initializeServerMigrationSettings(config);
  initializeTransportSettings();
  initializeFizzContext();

  std::vector<QuicVersion> supportedVersions{{QuicVersion::MVFST,
                                              QuicVersion::MVFST_EXPERIMENTAL,
                                              QuicVersion::MVFST_ALIAS,
                                              QuicVersion::QUIC_V1,
                                              QuicVersion::QUIC_DRAFT}};
  quicServer_->setSupportedVersion(supportedVersions);

  uint16_t managementPort = config["managementPort"].asInt();
  migrationManagement_ = std::make_shared<MigrationManagementInterface>(
      host_, managementPort, &evb_, quicServer_);

  quicServer_->setQuicServerTransportFactory(
      std::make_unique<TransportFactory>(std::move(migrationProtocols_),
                                         std::move(poolMigrationAddresses_),
                                         migrationManagement_,
                                         config["seed"].asInt()));
}

void Server::start() {
  folly::SocketAddress address(host_, port_);
  LOG(INFO) << "Starting server at " << address.describe();
  quicServer_->start(address, numberOfWorkerThreads_);
  quicServer_->waitUntilInitialized();
  migrationManagement_->start();
  evb_.loopForever();
  LOG(INFO) << "Stopping the server";
  migrationManagement_->dumpMigrationNotificationTimeToFile();
}

} // namespace quic::samples::servermigration
