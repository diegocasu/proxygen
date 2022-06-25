#include <proxygen/httpserver/samples/server-migration/app/common/Utils.h>

namespace quic::samples::servermigration {

std::string migrationProtocolsToString(
    const std::unordered_set<ServerMigrationProtocol>& migrationProtocols) {
  std::string result;
  for (const auto& protocol : migrationProtocols) {
    result += serverMigrationProtocolToString(protocol);
    result += ", ";
  }
  if (!result.empty()) {
    result.pop_back();
    result.pop_back();
  }
  return result;
}

std::string poolMigrationAddressesToString(
    const std::unordered_set<QuicIPAddress, QuicIPAddressHash>& pool) {
  std::string result;
  for (const auto& address : pool) {
    result += quicIPAddressToString(address);
    result += ", ";
  }
  if (!result.empty()) {
    result.pop_back();
    result.pop_back();
  }
  return result;
}

std::string managementCommandToJsonString(
    const MigrationManagementInterface::Command& command) {
  folly::dynamic dynamic = folly::dynamic::object();
  switch (command.action) {
    case MigrationManagementInterface::Action::ON_IMMINENT_SERVER_MIGRATION:
      if (!command.protocol) {
        throw std::invalid_argument("Missing \"protocol\" field");
      }
      if (command.protocol == ServerMigrationProtocol::EXPLICIT &&
          !command.address) {
        throw std::invalid_argument("Missing \"address\" field");
      }
      dynamic["action"] = "onImminentServerMigration";
      dynamic["protocol"] =
          serverMigrationProtocolToString(command.protocol.value());
      if (command.address) {
        dynamic["address"] = command.address->describe();
      }
      return folly::toJson(dynamic);
    case MigrationManagementInterface::Action::ON_NETWORK_SWITCH:
      dynamic["action"] = "onNetworkSwitch";
      return folly::toJson(dynamic);
    case MigrationManagementInterface::Action::SHUTDOWN:
      dynamic["action"] = "shutdown";
      return folly::toJson(dynamic);
  }
  folly::assume_unreachable();
}

MigrationManagementInterface::Command managementCommandFromJsonString(
    const std::string& command) {
  auto dynamic = folly::parseJson(command);
  MigrationManagementInterface::Command parsedCommand;

  auto actionField = dynamic["action"].asString();
  if (actionField == "onImminentServerMigration") {
    parsedCommand.action =
        MigrationManagementInterface::Action::ON_IMMINENT_SERVER_MIGRATION;
  } else if (actionField == "onNetworkSwitch") {
    parsedCommand.action =
        MigrationManagementInterface::Action::ON_NETWORK_SWITCH;
    return parsedCommand;
  } else if (actionField == "shutdown") {
    parsedCommand.action = MigrationManagementInterface::Action::SHUTDOWN;
    return parsedCommand;
  } else {
    throw std::runtime_error("Bad action");
  }

  auto protocolField = dynamic["protocol"].asString();
  if (protocolField == "Explicit") {
    auto addressField = dynamic["address"].asString();
    folly::SocketAddress address;
    address.setFromIpPort(addressField);
    parsedCommand.address = std::move(address);
    parsedCommand.protocol = ServerMigrationProtocol::EXPLICIT;
  } else if (protocolField == "Pool of Addresses") {
    parsedCommand.protocol = ServerMigrationProtocol::POOL_OF_ADDRESSES;
  } else if (protocolField == "Symmetric") {
    parsedCommand.protocol = ServerMigrationProtocol::SYMMETRIC;
  } else if (protocolField == "Synchronized Symmetric") {
    parsedCommand.protocol = ServerMigrationProtocol::SYNCHRONIZED_SYMMETRIC;
  } else {
    throw std::runtime_error("Bad protocol");
  }
  return parsedCommand;
}

} // namespace quic::samples::servermigration
