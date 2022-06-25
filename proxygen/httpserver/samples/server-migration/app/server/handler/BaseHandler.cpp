#include <proxygen/httpserver/samples/server-migration/app/server/handler/BaseHandler.h>

namespace quic::samples::servermigration {

void BaseHandler::setTransaction(
    proxygen::HTTPTransaction* transaction) noexcept {
  transaction_ = transaction;
}

void BaseHandler::detachTransaction() noexcept {
  delete this;
}

void BaseHandler::onTrailers(
    std::unique_ptr<proxygen::HTTPHeaders> /*trailers*/) noexcept {
  VLOG(1) << "Ignoring onTrailers";
}

void BaseHandler::onUpgrade(proxygen::UpgradeProtocol /*protocol*/) noexcept {
  VLOG(1) << "Ignoring onUpgrade";
}

void BaseHandler::onEgressPaused() noexcept {
  VLOG(1) << "Ignoring onEgressPaused";
}

void BaseHandler::onEgressResumed() noexcept {
  VLOG(1) << "Ignoring onEgressResumed";
}

} // namespace quic::samples::servermigration
