#include <iostream>
#include <boost/dynamic_bitset.hpp>

int main(int, char**){
    boost::dynamic_bitset<> db(10);
    db.set(3);
    std::cout << db<<std::endl;
    std::cout << "Hello, from ProductAutomata!\n";
}
