#pragma once

#include <fizz/protocol/CertificateVerifier.h>

namespace quic::samples::servermigration {

class DummyCertificateVerifier : public fizz::CertificateVerifier {
 public:
  ~DummyCertificateVerifier() override = default;

  void verify(const std::vector<std::shared_ptr<const fizz::PeerCert>>&)
      const override {
    return;
  }

  std::vector<fizz::Extension> getCertificateRequestExtensions()
      const override {
    return std::vector<fizz::Extension>();
  }
};

} // namespace quic::samples::servermigration
