#include <iostream>
#include <boost/dynamic_bitset.hpp>
#include <gmp.h>
#include <stdio.h>
#include <iostream>
#include <mp++/mp++.hpp>

using int_t = mppp::integer<1>;

int main()
{
    boost::dynamic_bitset<> db(10);
    db.set(3);
    std::cout << db<<std::endl;
    std::cout << "Hello, from ProductAutomata!\n";
    int_t n{42};
    std::cout << n << '\n';
}
