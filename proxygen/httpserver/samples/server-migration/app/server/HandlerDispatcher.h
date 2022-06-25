#pragma once

#include <proxygen/lib/http/session/HTTPTransaction.h>
#include <random>

namespace quic::samples::servermigration {

/**
 * Dispatcher that, given the path of an HTTP request,
 * creates and returns an appropriate handler.
 */
class HandlerDispatcher {
 public:
  HandlerDispatcher(const uint32_t& seed);
  ~HandlerDispatcher() = default;

  proxygen::HTTPTransactionHandler* getRequestHandler(
      proxygen::HTTPMessage* message);

 private:
  uint32_t seed_;
  std::shared_ptr<std::mt19937> prng_;
  std::shared_ptr<std::discrete_distribution<>>
      getResponseBodyDimensionDistribution_;
};

} // namespace quic::samples::servermigration
