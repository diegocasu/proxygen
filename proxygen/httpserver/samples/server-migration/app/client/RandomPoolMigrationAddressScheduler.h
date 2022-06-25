#pragma once

#include <quic/servermigration/PoolMigrationAddressSchedulerFactory.h>
#include <random>
#include <set>
#include <unordered_set>

namespace quic::samples::servermigration {

class RandomPoolMigrationAddressSchedulerFactory
    : public PoolMigrationAddressSchedulerFactory {
 public:
  explicit RandomPoolMigrationAddressSchedulerFactory(uint32_t seed);
  ~RandomPoolMigrationAddressSchedulerFactory() override = default;
  std::shared_ptr<PoolMigrationAddressScheduler> make() override;

 private:
  uint32_t seed_;
};

/**
 * Scheduler of pool migration addresses that selects the next address
 * at random. At each cycle, it extracts a random permutation of the
 * addresses, including the current server address, and iterates it; each
 * possible permutation of the pool has equal probability of appearance, as
 * granted by std::shuffle. The random number generation is enabled by
 * std::mt19937 (Mersenne Twister).
 * The scheduler uses both an std::set and an std::unordered_set to manage
 * the addresses, thus:
 * 1) the complexity of insert() and contains(const QuicIPAddress& address) is
 * the same of insert() and count() offered by std::set, respectively;
 * 2) the complexity of contains(const folly::SocketAddress& address) is the
 * same of count() offered by std::unordered_set.
 */
class RandomPoolMigrationAddressScheduler
    : public PoolMigrationAddressScheduler {
 public:
  ~RandomPoolMigrationAddressScheduler() override = default;
  RandomPoolMigrationAddressScheduler(uint32_t seed);

  RandomPoolMigrationAddressScheduler(
      const RandomPoolMigrationAddressScheduler&) = delete;
  RandomPoolMigrationAddressScheduler(
      RandomPoolMigrationAddressScheduler&& that) = delete;
  RandomPoolMigrationAddressScheduler& operator=(
      const RandomPoolMigrationAddressScheduler&) = delete;
  RandomPoolMigrationAddressScheduler& operator=(
      RandomPoolMigrationAddressScheduler&& that) = delete;

  /**
   * Inserts a new address in the scheduler, if not already present.
   * The insertion of an address while cycling the pool does not alter the
   * current cycle, i.e. the insertion has effect only starting from
   * the next cycle.
   * @param address  the address. It is ignored if all-zero.
   */
  void insert(QuicIPAddress address) override;

  /**
   * Returns the next address in the cycle, advancing it. If an address added
   * with insert() is equal to the current server address, this method
   * guarantees that it will be returned only once per cycle.
   * It throws a QuicInternalException exception if the scheduler is empty,
   * namely if one of the following conditions is true:
   * 1) no address has been added with insert();
   * 2) one address has been added with insert(), but it is equal to the
   * current server address.
   * @return  the next address in the cycle.
   */
  const QuicIPAddress& next() override;

  bool contains(const QuicIPAddress& address) override;
  bool contains(const folly::SocketAddress& address) override;
  void restart() override;

  /**
   * Sets the current address of the server. If a cycle is ongoing,
   * the operation is effective only starting from the next cycle.
   * @param address  the current address of the server.
   *                 If all-zero, it resets the address.
   */
  void setCurrentServerAddress(QuicIPAddress address) override;

  const QuicIPAddress& getCurrentServerAddress() override;

 protected:
  QuicIPAddress currentServerAddress_;
  QuicIPAddress pendingServerAddress_;
  std::set<QuicIPAddress> pool_;
  std::unordered_set<folly::SocketAddress> socketAddresses_;
  std::mt19937 prng_;
  uint32_t seed_;
  folly::Optional<std::vector<QuicIPAddress>> addressPermutation_;
  bool iterating_{false};
  std::vector<QuicIPAddress>::const_iterator iterator_;
};

} // namespace quic::samples::servermigration
