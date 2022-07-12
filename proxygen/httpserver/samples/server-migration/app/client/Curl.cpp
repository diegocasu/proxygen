#include <proxygen/httpserver/samples/server-migration/app/client/Curl.h>

namespace quic::samples::servermigration {

void Curl::setupHeaders(proxygen::HTTPMessage& request,
                        const proxygen::HTTPMethod& httpMethod,
                        const proxygen::URL& url) {
  request.setMethod(httpMethod);
  request.setHTTPVersion(3, 0);
  request.setURL(url.makeRelativeURL());
  request.setSecure(url.isSecure());
  request.getHeaders().add(proxygen::HTTP_HEADER_USER_AGENT, "proxygen_curl");
  request.getHeaders().add(proxygen::HTTP_HEADER_HOST, url.getHostAndPort());
  request.getHeaders().add("Accept", "*/*");
}

void Curl::sendRequest(proxygen::HTTPTransaction* transaction,
                       const proxygen::HTTPMethod& httpMethod,
                       const proxygen::URL& url,
                       std::unique_ptr<folly::IOBuf> body) {
  responseBaton_.reset();
  transaction_ = transaction;
  proxygen::HTTPMessage request;
  setupHeaders(request, httpMethod, url);
  transaction_->sendHeaders(request);
  if (httpMethod == proxygen::HTTPMethod::POST && body) {
    transaction_->sendBody(std::move(body));
  }
  transaction_->sendEOM();
  VLOG(1) << "Sent request" << request;
}

void Curl::connectSuccess(proxygen::HTTPUpstreamSession* /*session*/) {
  VLOG(1) << "Curl ignoring connectSuccess";
}

void Curl::connectError(const folly::AsyncSocketException& exception) {
  LOG(ERROR) << "Error while connecting: " << exception.what();
  responseBaton_.post();
}

void Curl::setTransaction(proxygen::HTTPTransaction* /*transaction*/) noexcept {
  VLOG(1) << "Ignoring setTransaction";
}

void Curl::detachTransaction() noexcept {
  VLOG(1) << "Ignoring detachTransaction";
}

void Curl::onHeadersComplete(
    std::unique_ptr<proxygen::HTTPMessage> message) noexcept {
  responseHeaders_ = std::move(message);
}

void Curl::onBody(std::unique_ptr<folly::IOBuf> chain) noexcept {
  VLOG(1) << fmt::format("onBody with chain of size={} bytes", chain->length());
  if (!responseBody_) {
    responseBody_ = std::move(chain);
  } else {
    size_t length = chain->length();
    responseBody_->appendToChain(std::move(chain));
    responseBody_->append(length);
  }
}

void Curl::onEOM() noexcept {
  responseAddress_ = transaction_->getPeerAddress();
  responseBaton_.post();
}

void Curl::onTrailers(
    std::unique_ptr<proxygen::HTTPHeaders> /*trailers*/) noexcept {
  VLOG(1) << "Ignoring onTrailers";
}

void Curl::onUpgrade(proxygen::UpgradeProtocol /*protocol*/) noexcept {
  VLOG(1) << "Ignoring onUpgrade";
}

void Curl::onError(const proxygen::HTTPException& error) noexcept {
  LOG(ERROR) << "Error: " << error.what();
}

void Curl::onEgressPaused() noexcept {
  VLOG(1) << "Ignoring onEgressPaused";
}

void Curl::onEgressResumed() noexcept {
  VLOG(1) << "Ignoring onEgressResumed";
}

std::unique_ptr<proxygen::HTTPMessage> Curl::getResponseHeaders() {
  return std::move(responseHeaders_);
}

std::unique_ptr<folly::IOBuf> Curl::getResponseBody() {
  return std::move(responseBody_);
}

const folly::SocketAddress& Curl::getResponseAddress() {
  return responseAddress_;
}

bool Curl::waitForResponse(const std::chrono::milliseconds& timeout) {
  VLOG(1) << "Waiting for response";
  return responseBaton_.try_wait_for(timeout);
}

} // namespace quic::samples::servermigration
