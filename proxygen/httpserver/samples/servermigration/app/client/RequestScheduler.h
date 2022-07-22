#pragma once

#include <chrono>
#include <folly/io/IOBuf.h>
#include <proxygen/httpserver/samples/servermigration/app/common/HttpPostBodyDistribution.h>
#include <proxygen/lib/http/HTTPMethod.h>
#include <proxygen/lib/utils/URL.h>
#include <random>

namespace quic::samples::servermigration {

/**
 * Scheduler that decides how to build the next request sent by the client,
 * in terms of URL, HTTP method and body size. If the sporadic pattern is
 * chosen, it also waits for the necessary amount of time before building
 * the next request.
 */
class RequestScheduler {
 public:
  enum class Pattern {
    SPORADIC,
    BACK_TO_BACK,
  };

  enum class Body {
    FIXED,
    FROM_DISTRIBUTION,
  };

  struct Request {
    proxygen::URL url;
    proxygen::HTTPMethod httpMethod;
    std::unique_ptr<folly::IOBuf> body;

    Request(proxygen::URL url,
            proxygen::HTTPMethod httpMethod,
            std::unique_ptr<folly::IOBuf> body);
  };

  RequestScheduler(const Pattern& pattern,
                   const int64_t& sporadicInterval,
                   const Body& body,
                   const uint32_t& seedRequestType,
                   const uint32_t& seedPostBodyDimension);
  Request nextRequest();

 private:
  std::unique_ptr<folly::IOBuf> createRandomBody(size_t size);

  Pattern pattern_;
  Body body_;
  std::chrono::seconds sporadicInterval_;
  bool firstRequest_{true};
  size_t fixedBodySize_{1024};

  // Attributes used to randomly extract the type of the request when using
  // Body::FROM_DISTRIBUTION. Extracting 0 means performing a POST request,
  // while extracting 1 means performing a GET request. The likelihood of
  // drawing out a POST is 0.22.
  std::mt19937 requestTypePrng_;
  uint32_t seedRequestType_;
  std::discrete_distribution<> requestTypeDistribution_{0.22, 0.78};

  // Attributes used to randomly extract the body of a POST request when using
  // Body::FROM_DISTRIBUTION. The index associated to a body size stored in
  // HttpPostBodyDistribution::values is extracted using the probabilities in
  // HttpPostBodyDistribution::probabilities.
  std::mt19937 postBodyDimensionPrng_;
  uint32_t seedPostBodyDimension_;
  std::discrete_distribution<> postBodyDimensionDistribution_{
      HttpPostBodyDistribution::probabilities.begin(),
      HttpPostBodyDistribution::probabilities.end()};
};

std::string toString(const RequestScheduler::Pattern& pattern);
std::string toString(const RequestScheduler::Body& body);

} // namespace quic::samples::servermigration
