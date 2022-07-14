#include <proxygen/httpserver/samples/servermigration/app/server/SessionController.h>
#include <proxygen/httpserver/samples/servermigration/app/server/TransportFactory.h>

namespace quic::samples::servermigration {

TransportFactory::TransportFactory(
    std::unordered_set<ServerMigrationProtocol> migrationProtocols,
    std::unordered_set<QuicIPAddress, QuicIPAddressHash> poolMigrationAddresses,
    std::shared_ptr<MigrationManagementInterface> migrationManagement,
    const int64_t &seed)
    : migrationProtocols_(std::move(migrationProtocols)),
      poolMigrationAddresses_(std::move(poolMigrationAddresses)),
      migrationManagement_(std::move(migrationManagement)),
      seedSequence_({seed}) {
  VLOG(1) << "Initializing the transport factory with master seed=" << seed;
  // Start generating an initial number of seeds for the clients.
  // More seeds will be generated later, if needed.
  seeds_.resize(incrementalSeedAllocation_);
  seedSequence_.generate(seeds_.begin(), seeds_.end());
}

uint32_t TransportFactory::getNextSeed() {
  std::lock_guard<std::mutex> guard(seedMutex_);
  if (nextSeed_ == seeds_.size()) {
    // Generate new seeds.
    seeds_.resize(seeds_.size() + incrementalSeedAllocation_);
    seedSequence_.generate(seeds_.begin(), seeds_.end());
  }
  uint32_t seed = seeds_[nextSeed_];
  ++nextSeed_;
  return seed;
}

QuicServerTransport::Ptr TransportFactory::make(
    folly::EventBase *evb,
    std::unique_ptr<folly::AsyncUDPSocket> socket,
    const folly::SocketAddress &,
    QuicVersion,
    std::shared_ptr<const fizz::server::FizzServerContext> context) noexcept {
  CHECK_EQ(evb, socket->getEventBase());
  VLOG(1) << "Creating new transport";

  // Session controller is self-owning, so a plain pointer is used.
  auto sessionController = new SessionController(getNextSeed());
  auto session = sessionController->createSession();
  auto transport = QuicServerTransport::make(
      evb, std::move(socket), session, session, context);

  if (!migrationProtocols_.empty()) {
    transport->allowServerMigration(migrationProtocols_);
  }
  if (!poolMigrationAddresses_.empty()) {
    for (const auto &address : poolMigrationAddresses_) {
      transport->addPoolMigrationAddress(address);
    }
  }
  if (migrationManagement_) {
    transport->setClientStateUpdateCallback(migrationManagement_);
    transport->setServerMigrationEventCallback(migrationManagement_);
  }

  sessionController->startSession(transport);
  return transport;
}

} // namespace quic::samples::servermigration