#pragma once

#include <proxygen/httpserver/samples/servermigration/app/server/MigrationManagementInterface.h>
#include <quic/QuicConstants.h>
#include <quic/codec/QuicIPAddress.h>

namespace quic::samples::servermigration {

/**
 * Converts a set of migration protocols to string.
 */
std::string migrationProtocolsToString(
    const std::unordered_set<ServerMigrationProtocol>& migrationProtocols);

/**
 * Converts a set of pool migration addresses to string.
 */
std::string poolMigrationAddressesToString(
    const std::unordered_set<QuicIPAddress, QuicIPAddressHash>& pool);

/**
 * Converts a command for the server migration management
 * interface to a JSON string.
 * @throws std::invalid_argument  if the command is missing mandatory fields.
 */
std::string managementCommandToJsonString(
    const MigrationManagementInterface::Command& command);

/**
 * Parses a command for the server migration management
 * interface from a JSON string.
 * @throws std::runtime_error  if the JSON string is malformed.
 */
MigrationManagementInterface::Command managementCommandFromJsonString(
    const std::string& command);

} // namespace quic::samples::servermigration
