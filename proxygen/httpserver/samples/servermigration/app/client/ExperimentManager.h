#pragma once

#include <folly/dynamic.h>
#include <folly/fibers/Baton.h>
#include <folly/io/async/AsyncUDPSocket.h>
#include <proxygen/lib/http/HTTPMethod.h>
#include <quic/QuicConstants.h>

namespace quic::samples::servermigration {

/**
 * Manager of an experiment. It is responsible of sending commands to the
 * server migration management interface and the container migration script,
 * at the time dictated by the experiment.
 */
class ExperimentManager
    : public folly::AsyncUDPSocket::ErrMessageCallback
    , public folly::AsyncUDPSocket::ReadCallback {
 public:
  explicit ExperimentManager(const folly::dynamic& config,
                             folly::EventBase* evb);
  void start();
  void maybeNotifyImminentServerMigration(
      const int64_t& numberOfCompletedRequests);

  /**
   * Returns true if a PTO must be artificially triggered on the client side
   * to proactively change the server address, i.e. if the Proactive Explicit
   * protocol must be used to handle the migration.
   */
  bool maybeTriggerServerMigration(const int64_t& numberOfCompletedRequests);

  bool maybeStopExperiment(const int64_t& numberOfCompletedRequests);
  void maybeSaveServiceTime(const int64_t& requestNumber,
                            const long& requestTimestamp,
                            const proxygen::HTTPMethod& requestMethod,
                            const std::size_t& requestBodySize,
                            const std::size_t& responseBodySize,
                            const long& serviceTime,
                            const folly::SocketAddress& serverAddress);
  void stopExperimentDueToTimeout();
  void dumpServiceTimesToFile();
  bool maybeCreateHandoverManager();

  /**
   * Updates the server management address after a server migration.
   * The management port is assumed to stay the same across migrations.
   * @param newServerAddress  the new server IP address.
   */
  void updateServerManagementAddress(const folly::IPAddress& newServerAddress);

  // AsyncUDPSocket::ErrMessageCallback methods.
  void errMessage(const cmsghdr& cmsg) noexcept override;
  void errMessageError(const folly::AsyncSocketException& ex) noexcept override;

  // AsyncUDPSocket::ReadCallback methods.
  void onReadError(const folly::AsyncSocketException& ex) noexcept override;
  void onReadClosed() noexcept override;
  void getReadBuffer(void** buf, size_t* len) noexcept override;
  void onDataAvailable(const folly::SocketAddress& client,
                       size_t len,
                       bool truncated,
                       OnDataAvailableParams params) noexcept override;

 private:
  enum class ExperimentId : int64_t {
    // Measure the service time of a normal QUIC connection,
    // without introducing server migration.
    QUIC_BASELINE = 0,

    // Experiment #1: measure the service time after server migration
    // depending only on the QUIC migration protocol.
    ONE = 1,

    // Experiment #2: measure the service time after server migration
    // depending on both the QUIC migration protocol and the container
    // migration.
    TWO = 2,

    // Experiment #3: measure migration notification time depending on
    // the number of clients and the migration protocol.
    THREE = 3,

    // Experiment #4: record service times over time when multiple
    // clients are connected, and the server migrates.
    FOUR = 4,

    // Experiment #5: record service times over time when server migration
    // is triggered by client handovers.
    FIVE = 5,

    // Experiment #6: record service times of the client while it migrates.
    // The server never migrates in this scenario. This is a baseline for
    // the experiment 5.
    CLIENT_MIGRATION_BASELINE = 6,

    MAX = CLIENT_MIGRATION_BASELINE,
  };

  void waitForResponseOrRetransmit(const folly::SocketAddress& destination,
                                   const std::string& message);
  void notifyImminentServerMigration();
  void triggerServerMigration(bool drain);
  void stopExperiment(bool shutdownContainerMigrationScript);

  // Information used to drive the experiment.
  ExperimentId experimentId_;
  int64_t notifyImminentMigrationAfterRequest_;
  int64_t triggerMigrationAfterRequest_;
  int64_t shutdownAfterRequest_;

  std::unique_ptr<folly::AsyncUDPSocket> socket_;
  std::unique_ptr<folly::IOBuf> readBuffer_;
  folly::fibers::Baton responseBaton_;
  std::chrono::milliseconds responseTimeout_{std::chrono::seconds(1)};
  unsigned int maxNumberOfRetransmissions_{5};
  std::chrono::seconds drainPeriod_{2};

  // Information used to contact the migration management interface
  // of the server to notify an imminent server migration or a shutdown.
  // The management address must be updated after a server migration,
  // so that subsequent commands can be correctly sent.
  folly::SocketAddress serverManagementAddress_;
  ServerMigrationProtocol migrationProtocol_;
  folly::SocketAddress migrationAddress_;
  bool proactiveExplicit_{false};

  // Information used to contact the container migration script
  // and trigger a container migration.
  folly::SocketAddress containerMigrationScriptAddress_;
  std::string migrateCommand_{"migrate"};

  // Significant service times measured during the experiment,
  // in microseconds, and related quantities.
  std::vector<long> requestTimestamps_;
  std::vector<long> serviceTimes_;
  std::vector<std::string> serverAddresses_;
  int64_t firstRequestAfterMigrationTriggered_{-1};
  std::string serviceTimesFile_{"service_times.json"};

  // Flag used in the second experiment to check
  // if migration was triggered or not.
  bool migrationTriggered_{false};

  // Flag used to record if the connection ended due to a timeout.
  // It is used only in the fourth experiment.
  bool connectionEndedDueToTimeout_{false};

  // Variables used during the second and fourth experiment to detect
  // when the first response from the new server address is received.
  folly::Optional<folly::SocketAddress> originalServerAddress_;
  bool firstResponseFromNewServerAddressReceived_{false};

  // Variables used during the second and fourth experiment
  // to determine when the experiment should end.
  int secondExpResponsesFromNewServerAddressBeforeShutdown_{10};
  int fourthExpResponsesFromNewServerAddressBeforeShutdown_{500};

  // Seed used in the third experiment to make the service times file unique.
  int64_t seed_;

  // Variables used in the fourth experiment to record HTTP
  // methods of requests, and request/response body sizes.
  std::vector<std::string> requestHttpMethods_;
  std::vector<std::size_t> requestBodySizes_;
  std::vector<std::size_t> responseBodySizes_;
};

} // namespace quic::samples::servermigration
