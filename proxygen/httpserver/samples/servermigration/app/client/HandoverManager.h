#pragma once

#include <folly/io/async/AsyncUDPSocket.h>
#include <folly/io/async/EventBase.h>
#include <folly/io/async/ScopedEventBaseThread.h>
#include <quic/client/QuicClientTransport.h>

namespace quic::samples::servermigration {

class HandoverManager
    : public folly::AsyncUDPSocket::ErrMessageCallback
    , public folly::AsyncUDPSocket::ReadCallback {
 public:
  HandoverManager(folly::EventBase* transportEvb,
                  std::shared_ptr<QuicClientTransport> quicClient);
  void start();

  // AsyncUDPSocket::ErrMessageCallback methods.
  void errMessage(const cmsghdr& cmsg) noexcept override;
  void errMessageError(const folly::AsyncSocketException& ex) noexcept override;

  // AsyncUDPSocket::ReadCallback methods.
  void onReadError(const folly::AsyncSocketException& ex) noexcept override;
  void onReadClosed() noexcept override;
  void getReadBuffer(void** buf, size_t* len) noexcept override;
  void onDataAvailable(const folly::SocketAddress& client,
                       size_t len,
                       bool truncated,
                       OnDataAvailableParams params) noexcept override;

 private:
  bool searchInOutputFile(const std::string& fileName, const std::string& str);
  bool doHandover(const folly::SocketAddress& newAddress,
                  const std::string& accessPoint,
                  const std::string& accessPointGateway,
                  const std::string& otherAccessPointSubnet,
                  const std::string& tcScriptPath);

  folly::EventBase* transportEvb_;
  std::shared_ptr<QuicClientTransport> quicClient_;
  folly::ScopedEventBaseThread managerThread_;
  std::unique_ptr<folly::AsyncUDPSocket> socket_;
  std::unique_ptr<folly::IOBuf> readBuffer_;
};

} // namespace quic::samples::servermigration