#pragma once

#include <proxygen/httpserver/samples/servermigration/app/server/MigrationManagementInterface.h>
#include <quic/server/QuicServerTransportFactory.h>

namespace quic::samples::servermigration {

/**
 * Factory used to create a QuicServerTransport object for each new connection.
 */
class TransportFactory : public QuicServerTransportFactory {
 public:
  TransportFactory(
      std::unordered_set<ServerMigrationProtocol> migrationProtocols,
      std::unordered_set<QuicIPAddress, QuicIPAddressHash>
          poolMigrationAddresses,
      std::shared_ptr<MigrationManagementInterface> migrationManagement,
      const int64_t& seed);

  QuicServerTransport::Ptr make(
      folly::EventBase* evb,
      std::unique_ptr<folly::AsyncUDPSocket> socket,
      const folly::SocketAddress&,
      QuicVersion,
      std::shared_ptr<const fizz::server::FizzServerContext> context) noexcept
      override;

 private:
  uint32_t getNextSeed();

  std::unordered_set<ServerMigrationProtocol> migrationProtocols_;
  std::unordered_set<QuicIPAddress, QuicIPAddressHash> poolMigrationAddresses_;
  std::shared_ptr<MigrationManagementInterface> migrationManagement_;
  std::seed_seq seedSequence_;
  std::vector<uint32_t> seeds_;
  size_t incrementalSeedAllocation_{100};
  size_t nextSeed_{0};
  std::mutex seedMutex_;
};

} // namespace quic::samples::servermigration
