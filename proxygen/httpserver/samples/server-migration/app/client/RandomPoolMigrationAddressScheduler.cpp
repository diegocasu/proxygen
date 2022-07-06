#include <proxygen/httpserver/samples/server-migration/app/client/RandomPoolMigrationAddressScheduler.h>
#include <quic/QuicConstants.h>
#include <quic/QuicException.h>

namespace quic::samples::servermigration {

RandomPoolMigrationAddressSchedulerFactory::
    RandomPoolMigrationAddressSchedulerFactory(uint32_t seed)
    : seed_(seed) {
}

std::shared_ptr<PoolMigrationAddressScheduler>
RandomPoolMigrationAddressSchedulerFactory::make() {
  return std::make_shared<RandomPoolMigrationAddressScheduler>(seed_);
}

RandomPoolMigrationAddressScheduler::RandomPoolMigrationAddressScheduler(
    uint32_t seed)
    : seed_(seed) {
  prng_.seed(seed_);
  VLOG(1) << "Initialized PoA scheduler with seed=" << seed_;
}

void RandomPoolMigrationAddressScheduler::setCurrentServerAddress(
    QuicIPAddress address) {
  if (!iterating_) {
    currentServerAddress_ = address;
    pendingServerAddress_ = currentServerAddress_;
    return;
  }
  pendingServerAddress_ = address;
}

const QuicIPAddress&
RandomPoolMigrationAddressScheduler::getCurrentServerAddress() {
  return currentServerAddress_;
}

bool RandomPoolMigrationAddressScheduler::contains(
    const QuicIPAddress& address) {
  return pool_.count(address);
}

bool RandomPoolMigrationAddressScheduler::contains(
    const folly::SocketAddress& address) {
  return socketAddresses_.count(address);
}

void RandomPoolMigrationAddressScheduler::insert(QuicIPAddress address) {
  if (address.isAllZero()) {
    return;
  }
  if (address.hasIPv4Field()) {
    socketAddresses_.insert(address.getIPv4AddressAsSocketAddress());
  }
  if (address.hasIPv6Field()) {
    socketAddresses_.insert(address.getIPv6AddressAsSocketAddress());
  }
  pool_.insert(address);
}

const QuicIPAddress& RandomPoolMigrationAddressScheduler::next() {
  if (pool_.empty()) {
    throw QuicInternalException(
        "Attempt to iterate through an empty address pool",
        LocalErrorCode::INTERNAL_ERROR);
  }

  if (!iterating_) {
    // First call of a cycle, so possibly update the current server address
    // and restart the cycle by generating a random permutation of the pool.
    iterating_ = true;
    currentServerAddress_ = pendingServerAddress_;

    addressPermutation_ =
        std::vector<QuicIPAddress>(pool_.begin(), pool_.end());
    if (!currentServerAddress_.isAllZero() &&
        !pool_.count(currentServerAddress_)) {
      addressPermutation_->push_back(currentServerAddress_);
    }
    std::shuffle(
        addressPermutation_->begin(), addressPermutation_->end(), prng_);

    iterator_ = addressPermutation_->cbegin();
  }

  auto& address = *iterator_;
  ++iterator_;
  if (iterator_ == addressPermutation_->cend()) {
    iterating_ = false;
  }
  return address;
}

void RandomPoolMigrationAddressScheduler::restart() {
  iterating_ = false;
  addressPermutation_.clear();
}

} // namespace quic::samples::servermigration
