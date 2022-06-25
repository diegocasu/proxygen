#include <proxygen/httpserver/samples/server-migration/app/server/SessionController.h>
#include <proxygen/lib/http/session/HQDownstreamSession.h>

namespace quic::samples::servermigration {

SessionController::SessionController(const uint32_t& seed)
    : handlerDispatcher_(seed) {
}

proxygen::HQSession* SessionController::createSession() {
  wangle::TransportInfo transportInfo;
  session_ = new proxygen::HQDownstreamSession(
      transactionsTimeout_, this, transportInfo, this);
  return session_;
}

void SessionController::startSession(std::shared_ptr<QuicSocket> socket) {
  CHECK(session_);
  session_->setSocket(std::move(socket));
  session_->startNow();
}

proxygen::HTTPTransactionHandler* SessionController::getRequestHandler(
    proxygen::HTTPTransaction& /*transaction*/,
    proxygen::HTTPMessage* message) {
  return handlerDispatcher_.getRequestHandler(message);
}

proxygen::HTTPTransactionHandler* FOLLY_NULLABLE
SessionController::getParseErrorHandler(
    proxygen::HTTPTransaction* /*transaction*/,
    const proxygen::HTTPException& /*error*/,
    const folly::SocketAddress& /*localAddress*/) {
  return nullptr;
}

proxygen::HTTPTransactionHandler* FOLLY_NULLABLE
SessionController::getTransactionTimeoutHandler(
    proxygen::HTTPTransaction* /*transaction*/,
    const folly::SocketAddress& /*localAddress*/) {
  return nullptr;
}

void SessionController::attachSession(proxygen::HTTPSessionBase* /*session*/) {
}

void SessionController::detachSession(
    const proxygen::HTTPSessionBase* /*session*/) {
  delete this;
}

} // namespace quic::samples::servermigration
