#pragma once

#include <proxygen/httpserver/samples/server-migration/app/server/handler/BaseHandler.h>

namespace quic::samples::servermigration {

/**
 * Handler that manages HTTP messages as follows:
 * 1) if the request is a POST, it sends back an HTTP response with empty body,
 * status code 200 and status message "OK";
 * 2) if the request is a GET, it sends back an HTTP response with a body whose
 * size is extracted from HttpGetResponseBodyDistribution.
 */
class DistributionHandler : public BaseHandler {
 public:
  DistributionHandler(std::shared_ptr<std::mt19937> prng,
                      std::shared_ptr<std::discrete_distribution<>>
                          getResponseBodyDimensionDistribution);
  ~DistributionHandler() override = default;

  void onHeadersComplete(
      std::unique_ptr<proxygen::HTTPMessage> message) noexcept override;
  void onBody(std::unique_ptr<folly::IOBuf> chain) noexcept override;
  void onEOM() noexcept override;
  void onError(const proxygen::HTTPException& error) noexcept override;

 private:
  std::unique_ptr<folly::IOBuf> createRandomBody(size_t size);

  std::shared_ptr<std::mt19937> prng_;
  std::shared_ptr<std::discrete_distribution<>>
      getResponseBodyDimensionDistribution_;
};

} // namespace quic::samples::servermigration
