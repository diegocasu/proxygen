#pragma once

#include <folly/dynamic.h>
#include <folly/io/async/ScopedEventBaseThread.h>
#include <proxygen/httpserver/samples/servermigration/app/client/Curl.h>
#include <proxygen/httpserver/samples/servermigration/app/client/ExperimentManager.h>
#include <proxygen/httpserver/samples/servermigration/app/client/HandoverManager.h>
#include <proxygen/httpserver/samples/servermigration/app/client/RequestScheduler.h>
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
    , public proxygen::HTTPSessionBase::InfoCallback
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

  // HTTPSessionBase::InfoCallback methods.
  void onDestroy(const proxygen::HTTPSessionBase& base) override;

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
  bool maybeUpdateServerManagementAddress();
  std::size_t getAndPrintReceivedResponse();
  bool isSessionClosed();

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
  std::chrono::milliseconds transactionsTimeout_{kDefaultIdleTimeout * 2};
  std::chrono::milliseconds connectionTimeout_{std::chrono::seconds(5)};
  bool connectionFailed_{false};

  // Attributes used to check if a server migration has been completed
  // and possibly store the new server address. They are useful to
  // decide when the server management address in the experiment
  // manager must be updated.
  std::mutex serverMigrationCompletedMutex_;
  folly::Optional<folly::IPAddress> newServerAddress_;

  // Attributes used to check if the HTTP session was closed due to an error.
  // Useful to avoid crashing the program before creating a new transaction.
  std::mutex sessionClosedMutex_;
  bool sessionClosed_{false};

  // Object used to change the transport socket
  // without errors during the client handovers.
  std::unique_ptr<HandoverManager> handoverManager_;
};

} // namespace quic::samples::servermigration
