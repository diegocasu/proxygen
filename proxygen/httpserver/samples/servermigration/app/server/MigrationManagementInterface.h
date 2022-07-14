#pragma once

#include <folly/io/async/AsyncUDPSocket.h>
#include <folly/io/async/EventBase.h>
#include <folly/json.h>
#include <quic/server/QuicServer.h>
#include <quic/servermigration/Callbacks.h>

namespace quic::samples::servermigration {

/**
 * Management interface to handle server migration.
 * It uses a UDP socket to receive commands, which are properly formatted
 * JSON strings. There are three classes of commands:
 *
 * 1) commands to notify an imminent server migration, used to let the server
 * prepare the migration (possibly inform clients about the event, block new
 * connections, etc.). Syntax:
 *
 * {
 *  "action": "onImminentServerMigration",
 *  "protocol": "PROTOCOL",
 *  "address": "IP:PORT"
 * }
 *
 * where "protocol" can be "Explicit", "Pool of Addresses", "Symmetric" or
 * "Synchronized Symmetric", and "address" is mandatory only if the protocol
 * is Explicit (otherwise, it is ignored).
 *
 * 2) commands to notify that a server migration has been completed. They are
 * used to let the server know that a migration has ended (possibly inform
 * clients about the event, unblock new connections, etc.). Syntax:
 *
 * {
 *  "action": "onNetworkSwitch"
 * }
 *
 * 3) commands to shutdown the server. Syntax:
 *
 * {
 *  "action": "shutdown"
 * }
 *
 */
class MigrationManagementInterface
    : public ClientStateUpdateCallback
    , public ServerMigrationEventCallback
    , public folly::AsyncUDPSocket::ErrMessageCallback
    , public folly::AsyncUDPSocket::ReadCallback {
 public:
  enum class Action {
    ON_IMMINENT_SERVER_MIGRATION,
    ON_NETWORK_SWITCH,
    SHUTDOWN
  };

  struct Command {
    Action action;
    folly::Optional<ServerMigrationProtocol> protocol;
    folly::Optional<folly::SocketAddress> address;
  };

  MigrationManagementInterface(std::string host,
                               uint16_t port,
                               folly::EventBase* evb,
                               std::shared_ptr<QuicServer> quicServer);
  ~MigrationManagementInterface() override = default;
  void start();
  void dumpMigrationNotificationTimeToFile();

  // ClientStateUpdateCallback methods.
  void onHandshakeFinished(
      folly::SocketAddress clientAddress,
      ConnectionId serverConnectionId,
      folly::Optional<std::unordered_set<ServerMigrationProtocol>>
          negotiatedProtocols) noexcept override;
  void onClientMigrationDetected(
      ConnectionId serverConnectionId,
      folly::SocketAddress newClientAddress) noexcept override;
  void onConnectionClose(ConnectionId serverConnectionId) noexcept override;

  // ServerMigrationEventCallback methods.
  void onPoolMigrationAddressAckReceived(
      ConnectionId serverConnectionId,
      PoolMigrationAddressFrame frame) noexcept override;
  void onServerMigrationAckReceived(
      ConnectionId serverConnectionId,
      ServerMigrationFrame frame) noexcept override;
  void onServerMigratedAckReceived(
      ConnectionId serverConnectionId) noexcept override;
  void onServerMigrationFailed(ConnectionId serverConnectionId,
                               ServerMigrationError error) noexcept override;
  void onServerMigrationReady(
      ConnectionId serverConnectionId) noexcept override;
  void onServerMigrationCompleted(
      ConnectionId serverConnectionId) noexcept override;

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
  void resetMigrationState();
  Command parseCommandFromReadBuffer(const size_t& len);
  void handleOnImminentServerMigrationCommand(
      const folly::SocketAddress& client,
      const MigrationManagementInterface::Command& command);
  void handleOnNetworkSwitchCommand(const folly::SocketAddress& client);
  void handleShutdownCommand(const folly::SocketAddress& client);

  enum TransportMigrationState {
    NOT_READY,
    READY,
    COMPLETED,
  };

  // Attributes used to manage the server migration process.
  // If multiple clients are connected to the server, then the map, the
  // counters and the flag could be accessed by multiple threads at the
  // same time, so they must be managed using a mutex.
  std::mutex migrationMutex_;
  bool migrationInProgress_{false};
  bool transportsReady_{false};
  bool networkSwitched_{false};
  unsigned int numberOfTransportsReady_{0};
  unsigned int numberOfTransportsMigrated_{0};
  std::unordered_map<ConnectionId, TransportMigrationState, ConnectionIdHash>
      transports_;

  // Attributes used to expose the interface.
  std::string host_;
  uint16_t port_;
  std::unique_ptr<folly::AsyncUDPSocket> socket_;
  std::unique_ptr<folly::IOBuf> readBuffer_;
  folly::EventBase* evb_;

  // Managed server.
  std::shared_ptr<QuicServer> quicServer_;

  // Migration notification time measured during the session. The value is
  // significant only if recorded during the third experiment, where a single
  // migration is performed with multiple clients connected at the same time.
  // Note that the migration notification time is recorded only if all the
  // clients become ready for the migration, thus it is not recorded when the
  // migration ready state is achieved due to:
  // 1) no clients connected to the server;
  // 2) one or more clients closing the connection.
  folly::Optional<std::chrono::time_point<std::chrono::steady_clock>>
      migrationNotificationReceptionTime_;
  folly::Optional<std::chrono::time_point<std::chrono::steady_clock>>
      migrationReadyTime_;
  std::string migrationNotificationTimeFile_{
      "migration_notification_time.json"};
};

} // namespace quic::samples::servermigration
