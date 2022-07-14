#include <proxygen/httpserver/samples/servermigration/app/common/HttpGetResponseBodyDistribution.h>
#include <proxygen/httpserver/samples/servermigration/app/server/HandlerDispatcher.h>
#include <proxygen/httpserver/samples/servermigration/app/server/handler/DistributionHandler.h>
#include <proxygen/httpserver/samples/servermigration/app/server/handler/EchoHandler.h>

namespace quic::samples::servermigration {

HandlerDispatcher::HandlerDispatcher(const uint32_t& seed) : seed_(seed) {
  VLOG(1) << "Initialized handler dispatcher with seed=" << seed;
  prng_ = std::make_shared<std::mt19937>();
  prng_->seed(seed_);
  getResponseBodyDimensionDistribution_ =
      std::make_shared<std::discrete_distribution<>>(
          HttpGetResponseBodyDistribution::probabilities.begin(),
          HttpGetResponseBodyDistribution::probabilities.end());
}

proxygen::HTTPTransactionHandler* HandlerDispatcher::getRequestHandler(
    proxygen::HTTPMessage* message) {
  auto path = message->getPathAsStringPiece();
  VLOG(1) << "Selecting request handler for endpoint=" << path;

  if (path == "/echo") {
    VLOG(1) << "EchoHandler selected";
    return new EchoHandler();
  }
  if (path == "/distribution") {
    VLOG(1) << "DistributionHandler selected";
    return new DistributionHandler(prng_,
                                   getResponseBodyDimensionDistribution_);
  }

  LOG(ERROR) << "No handler for the endpoint. Stopping the server";
  folly::assume_unreachable();
}

} // namespace quic::samples::servermigration
