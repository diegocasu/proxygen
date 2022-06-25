#pragma once

#include <folly/dynamic.h>
#include <folly/io/async/ScopedEventBaseThread.h>
#include <proxygen/httpserver/samples/server-migration/app/client/Curl.h>
#include <proxygen/httpserver/samples/server-migration/app/client/ExperimentManager.h>
#include <proxygen/httpserver/samples/server-migration/app/client/RequestScheduler.h>
#include <proxygen/lib/http/session/HQUpstreamSession.h>
#include <quic/client/QuicClientTransport.h>
#include <quic/fizz/client/handshake/FizzClientQuicHandshakeContext.h>
#include <random>

namespace quic::samples::servermigration {

/**
 * HTTP/3 client using an extended version of mvfst to support
 * server migration at the transport layer.
 * It sends requests with the patterns specified in the configuration file.
 */
class Client
    : public proxygen::HQSession::ConnectCallback
    , public quic::ServerMigrationEventCallback
    , public std::enable_shared_from_this<Client> {
 public:
  explicit Client(const folly::dynamic& config);
  ~Client() override = default;
  void start();

  // HQSession::ConnectCallback methods.
  void onReplaySafe() override;
  void connectError(quic::QuicError error) override;

  // ServerMigrationEventCallback methods.
  void onPoolMigrationAddressReceived(
      PoolMigrationAddressFrame frame) noexcept override;
  void onServerMigrationReceived(ServerMigrationFrame frame) noexcept override;
  void onServerMigratedReceived() noexcept override;
  void onServerMigrationProbingStarted(
      ServerMigrationProtocol protocol,
      folly::SocketAddress address) noexcept override;
  void onServerMigrationCompleted() noexcept override;

 private:
  struct Seeds {
    int64_t master;
    uint32_t poaScheduler;
    uint32_t requestType;
    uint32_t postBodyDimension;
  };

  std::shared_ptr<fizz::client::FizzClientContext> createFizzContext();
  std::shared_ptr<FizzClientQuicHandshakeContext> createFizzHandshakeContext(
      const folly::dynamic& config);
  void initializeServerMigrationSettings(const folly::dynamic& config);
  void initializeTransportSettings();
  void initializeRequestScheduler(const folly::dynamic& config);
  void generateSeeds();
  void scheduleRequests();

  std::string serverHost_;
  uint16_t serverPort_;
  std::shared_ptr<QuicClientTransport> quicClient_;
  std::unique_ptr<Curl> curl_;
  std::unique_ptr<RequestScheduler> requestScheduler_;
  std::unique_ptr<ExperimentManager> experimentManager_;
  proxygen::HQUpstreamSession* session_;
  folly::ScopedEventBaseThread networkThread_;
  folly::fibers::Baton startDone_;
  std::seed_seq seedSequence_;
  Seeds seeds_;
  std::chrono::milliseconds transactionsTimeout_{kDefaultIdleTimeout};
  std::chrono::milliseconds connectionTimeout_{std::chrono::seconds(5)};
  bool connectionFailed_{false};
};

} // namespace quic::samples::servermigration
