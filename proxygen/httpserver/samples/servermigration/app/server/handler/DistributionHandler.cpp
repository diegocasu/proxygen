#include <folly/Random.h>
#include <proxygen/httpserver/samples/servermigration/app/common/HttpGetResponseBodyDistribution.h>
#include <proxygen/httpserver/samples/servermigration/app/server/handler/DistributionHandler.h>

namespace quic::samples::servermigration {

DistributionHandler::DistributionHandler(
    std::shared_ptr<std::mt19937> prng,
    std::shared_ptr<std::discrete_distribution<>>
        getResponseBodyDimensionDistribution)
    : prng_(std::move(prng)),
      getResponseBodyDimensionDistribution_(
          std::move(getResponseBodyDimensionDistribution)) {
}

std::unique_ptr<folly::IOBuf> DistributionHandler::createRandomBody(
    size_t size) {
  auto body = folly::IOBuf::create(size);
  folly::Random::secureRandom(body->writableData(), size);
  body->append(size);
  return body;
}

void DistributionHandler::onHeadersComplete(
    std::unique_ptr<proxygen::HTTPMessage> message) noexcept {
  VLOG(1) << "Received message headers" << *message;
  proxygen::HTTPMessage response;
  response.setVersionString("3.0");
  response.setStatusCode(200);
  response.setStatusMessage("OK");
  response.setWantsKeepalive(true);
  transaction_->sendHeaders(response);
  VLOG(1) << "Sending response headers" << response;

  auto method = message->getMethod();
  if (method == proxygen::HTTPMethod::GET) {
    auto& distribution = *getResponseBodyDimensionDistribution_;
    auto& prng = *prng_;
    size_t bodySizeIndex = distribution(prng);
    size_t bodySize = HttpGetResponseBodyDistribution::values[bodySizeIndex];
    auto body = createRandomBody(bodySize);
    VLOG(1) << fmt::format("Sending response body of size={} bytes",
                           body->length());
    transaction_->sendBody(std::move(body));
  }
}

void DistributionHandler::onBody(std::unique_ptr<folly::IOBuf> chain) noexcept {
  VLOG(1) << fmt::format("Received request body with chain of size={} bytes",
                         chain->length());
}

void DistributionHandler::onEOM() noexcept {
  transaction_->sendEOM();
}

void DistributionHandler::onError(
    const proxygen::HTTPException& error) noexcept {
  LOG(ERROR) << "Error: " << error.what();
  transaction_->sendAbort();
}

} // namespace quic::samples::servermigration
