#pragma once

#include <folly/dynamic.h>
#include <proxygen/httpserver/samples/server-migration/app/server/MigrationManagementInterface.h>
#include <quic/QuicConstants.h>
#include <quic/server/QuicServer.h>

namespace quic::samples::servermigration {

/**
 * HTTP/3 server using an extended version of mvfst to support server migration
 * at the transport layer. The server can be notified about an imminent server
 * migration or a completed migration by sending specific commands to its
 * management interface.
 */
class Server {
 public:
  explicit Server(const folly::dynamic& config);
  void start();

 private:
  void initializeServerMigrationSettings(const folly::dynamic& config);
  void initializeTransportSettings();
  void initializeFizzContext();

  std::string host_;
  uint16_t port_;
  size_t numberOfWorkerThreads_;
  std::shared_ptr<QuicServer> quicServer_;
  std::unordered_set<ServerMigrationProtocol> migrationProtocols_;
  std::unordered_set<QuicIPAddress, QuicIPAddressHash> poolMigrationAddresses_;
  std::shared_ptr<MigrationManagementInterface> migrationManagement_;
  folly::EventBase evb_;
};

} // namespace quic::samples::servermigration
