#pragma once

#include <proxygen/httpserver/samples/servermigration/app/server/HandlerDispatcher.h>
#include <proxygen/lib/http/session/HQSession.h>
#include <proxygen/lib/http/session/HTTPSessionController.h>

namespace quic::samples::servermigration {

/**
 * HTTP/3 session controller linked to a single QuicServerTransport.
 * It is self-owning, so there is no need to keep track of them for
 * memory deallocation purposes.
 */
class SessionController
    : public proxygen::HTTPSessionController
    , public proxygen::HTTPSessionBase::InfoCallback {
 public:
  SessionController(const uint32_t& seed);
  ~SessionController() override = default;
  proxygen::HQSession* createSession();
  void startSession(std::shared_ptr<quic::QuicSocket> socket);

  // HTTPSessionController methods.
  proxygen::HTTPTransactionHandler* getRequestHandler(
      proxygen::HTTPTransaction& transaction,
      proxygen::HTTPMessage* message) override;

  proxygen::HTTPTransactionHandler* getParseErrorHandler(
      proxygen::HTTPTransaction* transaction,
      const proxygen::HTTPException& error,
      const folly::SocketAddress& localAddress) override;

  proxygen::HTTPTransactionHandler* getTransactionTimeoutHandler(
      proxygen::HTTPTransaction* transaction,
      const folly::SocketAddress& localAddress) override;

  void attachSession(proxygen::HTTPSessionBase* session) override;
  void detachSession(const proxygen::HTTPSessionBase* session) override;

 private:
  // Plain pointer to avoid circular references.
  proxygen::HQSession* session_{nullptr};
  HandlerDispatcher handlerDispatcher_;
  std::chrono::milliseconds transactionsTimeout_{kDefaultIdleTimeout};
};

} // namespace quic::samples::servermigration
