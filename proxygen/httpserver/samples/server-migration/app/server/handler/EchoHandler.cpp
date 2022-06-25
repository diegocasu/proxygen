#include <proxygen/httpserver/samples/server-migration/app/server/handler/EchoHandler.h>

namespace quic::samples::servermigration {

void EchoHandler::onHeadersComplete(
    std::unique_ptr<proxygen::HTTPMessage> message) noexcept {
  VLOG(1) << "Received message headers" << *message;
  proxygen::HTTPMessage response;
  response.setVersionString("3.0");
  response.setStatusCode(200);
  response.setStatusMessage("OK");
  response.setWantsKeepalive(true);
  message->getHeaders().forEach(
      [&](const std::string& header, const std::string& value) {
        response.getHeaders().add(header, value);
      });
  transaction_->sendHeaders(response);
  VLOG(1) << "Sending response headers" << response;
}

void EchoHandler::onBody(std::unique_ptr<folly::IOBuf> chain) noexcept {
  VLOG(1) << fmt::format("Received request body with chain of size={} bytes",
                         chain->length());
  VLOG(1) << fmt::format("Sending response body with chain of size={} bytes",
                         chain->length());
  transaction_->sendBody(std::move(chain));
}

void EchoHandler::onEOM() noexcept {
  transaction_->sendEOM();
}

void EchoHandler::onError(const proxygen::HTTPException& error) noexcept {
  LOG(ERROR) << "Error: " << error.what();
  transaction_->sendAbort();
}

} // namespace quic::samples::servermigration
