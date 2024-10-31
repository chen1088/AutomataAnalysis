#include <iostream>
#include <boost/dynamic_bitset.hpp>
#include <gmp.h>
int main(int, char**){
    boost::dynamic_bitset<> db(10);
    db.set(3);
    std::cout << db<<std::endl;
    std::cout << "Hello, from ProductAutomata!\n";
    mpz_t a;
    mpz_init(a);
    mpz_set_ui(a, 10);
    mpz_out_str(stdout,10,a);
    std::cout << a << std::endl;
}
