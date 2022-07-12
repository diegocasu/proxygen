#pragma once

#include <folly/fibers/Baton.h>
#include <proxygen/lib/http/HTTPConnector.h>
#include <proxygen/lib/http/session/HTTPTransaction.h>
#include <proxygen/lib/utils/URL.h>

namespace quic::samples::servermigration {

/**
 * URL client that manages HTTP transactions by
 * sending requests and receiving responses.
 */
class Curl
    : public proxygen::HTTPConnector::Callback
    , public proxygen::HTTPTransactionHandler {

 public:
  Curl() = default;
  ~Curl() override = default;

  void sendRequest(proxygen::HTTPTransaction* transaction,
                   const proxygen::HTTPMethod& httpMethod,
                   const proxygen::URL& url,
                   std::unique_ptr<folly::IOBuf> body);
  bool waitForResponse(const std::chrono::milliseconds& timeout);
  std::unique_ptr<proxygen::HTTPMessage> getResponseHeaders();
  std::unique_ptr<folly::IOBuf> getResponseBody();
  const folly::SocketAddress& getResponseAddress();

  // HTTPConnector::Callback methods.
  void connectSuccess(proxygen::HTTPUpstreamSession* session) override;
  void connectError(const folly::AsyncSocketException& exception) override;

  // HTTPTransactionHandler methods.
  void setTransaction(proxygen::HTTPTransaction* transaction) noexcept override;
  void detachTransaction() noexcept override;
  void onHeadersComplete(
      std::unique_ptr<proxygen::HTTPMessage> message) noexcept override;
  void onBody(std::unique_ptr<folly::IOBuf> chain) noexcept override;
  void onTrailers(
      std::unique_ptr<proxygen::HTTPHeaders> trailers) noexcept override;
  void onEOM() noexcept override;
  void onUpgrade(proxygen::UpgradeProtocol protocol) noexcept override;
  void onError(const proxygen::HTTPException& error) noexcept override;
  void onEgressPaused() noexcept override;
  void onEgressResumed() noexcept override;

 private:
  void setupHeaders(proxygen::HTTPMessage& request,
                    const proxygen::HTTPMethod& httpMethod,
                    const proxygen::URL& url);

  proxygen::HTTPTransaction* transaction_{nullptr};
  std::unique_ptr<proxygen::HTTPMessage> responseHeaders_;
  std::unique_ptr<folly::IOBuf> responseBody_;
  folly::SocketAddress responseAddress_;
  folly::fibers::Baton responseBaton_;
};

} // namespace quic::samples::servermigration
