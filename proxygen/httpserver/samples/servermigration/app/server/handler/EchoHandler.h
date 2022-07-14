#pragma once

#include <proxygen/httpserver/samples/servermigration/app/server/handler/BaseHandler.h>

namespace quic::samples::servermigration {

/**
 * Handler that echoes back the HTTP message.
 */
class EchoHandler : public BaseHandler {
 public:
  EchoHandler() = default;
  ~EchoHandler() override = default;

  void onHeadersComplete(
      std::unique_ptr<proxygen::HTTPMessage> message) noexcept override;
  void onBody(std::unique_ptr<folly::IOBuf> chain) noexcept override;
  void onEOM() noexcept override;
  void onError(const proxygen::HTTPException& error) noexcept override;
};

} // namespace quic::samples::servermigration
