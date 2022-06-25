#include <folly/Random.h>
#include <proxygen/httpserver/samples/server-migration/app/client/RequestScheduler.h>
#include <thread>
#include <utility>

namespace quic::samples::servermigration {

RequestScheduler::Request::Request(proxygen::URL url,
                                   proxygen::HTTPMethod httpMethod,
                                   std::unique_ptr<folly::IOBuf> body)
    : url(std::move(url)), httpMethod(httpMethod), body(std::move(body)) {
}

RequestScheduler::RequestScheduler(const Pattern& pattern,
                                   const Body& body,
                                   const uint32_t& seedRequestType,
                                   const uint32_t& seedPostBodyDimension)
    : pattern_(pattern),
      body_(body),
      seedRequestType_(seedRequestType),
      seedPostBodyDimension_(seedPostBodyDimension) {
  requestTypePrng_.seed(seedRequestType_);
  postBodyDimensionPrng_.seed(seedPostBodyDimension_);
  VLOG(1) << fmt::format(
      "Initialized request scheduler with pattern={}, body={}, "
      "seed request type={}, seed POST body={}",
      toString(pattern),
      toString(body),
      seedRequestType_,
      seedPostBodyDimension_);
}

std::unique_ptr<folly::IOBuf> RequestScheduler::createRandomBody(size_t size) {
  auto body = folly::IOBuf::create(size);
  folly::Random::secureRandom(body->writableData(), size);
  body->append(size);
  return body;
}

RequestScheduler::Request RequestScheduler::nextRequest() {
  if (pattern_ == Pattern::SPORADIC && !firstRequest_) {
    VLOG(1) << fmt::format(
        "Waiting for {} seconds before generating the next request",
        sporadicPeriod_.count());
    std::this_thread::sleep_for(sporadicPeriod_);
  }
  firstRequest_ = false;

  switch (body_) {
    case Body::FIXED: {
      proxygen::URL url("/echo", true);
      auto body = createRandomBody(fixedBodySize_);
      VLOG(1) << fmt::format(
          "Generated request with url=/echo, method=POST, body size={} bytes",
          body->length());
      return {url, proxygen::HTTPMethod::POST, std::move(body)};
    }
    case Body::FROM_DISTRIBUTION: {
      // First step: choose if the request will be a GET or a POST.
      std::array<proxygen::HTTPMethod, 2> methods{proxygen::HTTPMethod::POST,
                                                  proxygen::HTTPMethod::GET};
      size_t index = requestTypeDistribution_(requestTypePrng_);
      auto chosenMethod = methods[index];

      // Second step: craft a request with an empty body (GET) or
      // a randomly sized body (POST).
      proxygen::URL url("/distribution", true);

      if (chosenMethod == proxygen::HTTPMethod::GET) {
        VLOG(1) << fmt::format(
            "Generated request with url=/distribution, method={}, "
            "body size=0 bytes",
            proxygen::methodToString(chosenMethod));
        return {url, chosenMethod, nullptr};
      }

      size_t bodySizeIndex =
          postBodyDimensionDistribution_(postBodyDimensionPrng_);
      size_t bodySize = HttpPostBodyDistribution::values[bodySizeIndex];
      auto body = createRandomBody(bodySize);
      VLOG(1) << fmt::format(
          "Generated request with url=/distribution, method={}, "
          "body size={} bytes",
          proxygen::methodToString(chosenMethod),
          body->length());
      return {url, chosenMethod, std::move(body)};
    }
  }
  folly::assume_unreachable();
}

std::string toString(const RequestScheduler::Pattern& pattern) {
  switch (pattern) {
    case RequestScheduler::Pattern::SPORADIC:
      return "sporadic";
    case RequestScheduler::Pattern::BACK_TO_BACK:
      return "back to back";
  }
  folly::assume_unreachable();
}

std::string toString(const RequestScheduler::Body& body) {
  switch (body) {
    case RequestScheduler::Body::FIXED:
      return "fixed";
    case RequestScheduler::Body::FROM_DISTRIBUTION:
      return "from distribution";
  }
  folly::assume_unreachable();
}

} // namespace quic::samples::servermigration
