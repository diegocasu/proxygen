#pragma once

#include <folly/dynamic.h>
#include <folly/fibers/Baton.h>
#include <folly/io/async/AsyncUDPSocket.h>
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
                            const long& serviceTime,
                            const folly::SocketAddress& serverAddress);
  void dumpServiceTimesToFile();

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
    // Experiment #1: measure the service time after server migration
    // depending only on the QUIC migration protocol.
    FIRST = 1,

    // Experiment #2: measure the service time after server migration
    // depending on both the QUIC migration protocol and the container
    // migration.
    SECOND = 2,
    MAX = SECOND
  };

  void waitForResponseOrRetransmit(const folly::SocketAddress& destination,
                                   const std::string& message);
  void handleFirstAndSecondExperimentNotifyImminentServerMigration();
  void handleFirstAndSecondExperimentTriggerServerMigration();
  void handleFirstAndSecondExperimentStopExperiment();

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
  bool proactiveExplicit_{false};
  // The migration address is valid only if the Explicit
  // protocol is chosen, otherwise it is empty.
  folly::Optional<folly::SocketAddress> migrationAddress_;

  // Information used to contact the container migration script
  // and trigger a container migration.
  folly::SocketAddress containerMigrationScriptAddress_;
  std::string migrateCommand_{"migrate"};

  // Significant service times measured during the experiment, in microseconds.
  std::vector<long> serviceTimes_;
  std::vector<std::string> serverAddresses_;
  std::string serviceTimesFile_{"service_times.json"};
};

} // namespace quic::samples::servermigration
