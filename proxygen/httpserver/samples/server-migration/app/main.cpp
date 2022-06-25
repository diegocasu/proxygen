#include <folly/BenchmarkUtil.h>
#include <folly/FileUtil.h>
#include <folly/init/Init.h>
#include <folly/json.h>
#include <folly/portability/GFlags.h>
#include <folly/ssl/Init.h>

#include <proxygen/httpserver/samples/server-migration/app/client/Client.h>
#include <proxygen/httpserver/samples/server-migration/app/server/Server.h>

DEFINE_string(mode, "", "Mode of operation, either \"client\" or \"server\"");
DEFINE_string(config, "", "Path of the JSON configuration file");

void setUp(int& argc, char* argv[]) {
#if FOLLY_HAVE_LIBGFLAGS
  // Enable glog logging to stderr by default.
  gflags::SetCommandLineOptionWithMode(
      "logtostderr", "1", gflags::SET_FLAGS_DEFAULT);
#endif
  folly::init(&argc, &argv, false);
  folly::ssl::init();
}

void validateCommandLineOptions() {
  if (FLAGS_mode != "client" && FLAGS_mode != "server") {
    throw std::invalid_argument(
        "Mode of operation must be either \"client\" or \"server\"");
  }
  if (FLAGS_config.empty()) {
    throw std::invalid_argument("Configuration file not specified");
  }
}

folly::dynamic parseConfigurationFile() {
  try {
    std::string configFile;
    folly::readFile(FLAGS_config.data(), configFile);
    configFile = folly::json::stripComments(configFile);
    return folly::parseJson(configFile);
  } catch (std::exception& exception) {
    throw std::invalid_argument(fmt::format(
        "Impossible to open and read the configuration file. Error={}",
        exception.what()));
  }
}

std::unique_ptr<unsigned char[]> maybeInflateMemoryFootprint(
    folly::dynamic& config) {
  auto configMemoryFootprint = config["memoryFootprintInflation"];
  if (configMemoryFootprint["enable"].asBool()) {
    return std::make_unique<unsigned char[]>(
        configMemoryFootprint["additionalBytes"].asInt());
  }
  return nullptr;
}

int main(int argc, char* argv[]) {
  setUp(argc, argv);
  validateCommandLineOptions();
  auto config = parseConfigurationFile();

  try {
    if (FLAGS_mode == "client") {
      // The client variable must be managed using a shared_ptr, because
      // Client class inherits from std::enable_shared_from_this.
      auto client =
          std::make_shared<quic::samples::servermigration::Client>(config);
      client->start();
    } else if (FLAGS_mode == "server") {
      // Pointer to an array used to artificially increase
      // the memory footprint of the application.
      std::unique_ptr<unsigned char[]> memoryInflater;
      folly::doNotOptimizeAway(memoryInflater =
                                   maybeInflateMemoryFootprint(config));

      quic::samples::servermigration::Server server(config);
      server.start();
    }
  } catch (const std::exception& exception) {
    LOG(ERROR) << "Fatal error. " << exception.what();
    return -1;
  }
  return 0;
}
