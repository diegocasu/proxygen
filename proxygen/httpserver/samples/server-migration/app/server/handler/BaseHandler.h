#pragma once

#include <proxygen/lib/http/session/HTTPTransaction.h>

namespace quic::samples::servermigration {

/**
 * Base handler from which all the handlers must inherit.
 */
class BaseHandler : public proxygen::HTTPTransactionHandler {
 public:
  BaseHandler() = default;
  virtual ~BaseHandler() override = default;

  void setTransaction(proxygen::HTTPTransaction* txn) noexcept override;
  void detachTransaction() noexcept override;
  void onTrailers(
      std::unique_ptr<proxygen::HTTPHeaders> /*trailers*/) noexcept override;
  void onUpgrade(proxygen::UpgradeProtocol /*protocol*/) noexcept override;
  void onEgressPaused() noexcept override;
  void onEgressResumed() noexcept override;

 protected:
  proxygen::HTTPTransaction* transaction_{nullptr};
};

} // namespace quic::samples::servermigration
