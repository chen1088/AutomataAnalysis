#pragma once
#include <mp++/mp++.hpp>
#include <map>
class orgf
{
   // This is the class of ordinary rational generating functions
public:
   orgf();
   ~orgf();
   
   // The following functions are the basic operations on generating functions
   // The functions are overloaded to handle different types of generating functions
   // The functions are implemented
   int numofvars = 1;
   std::map<mppp::integer<1>, mppp::rational<1>> num_coeffs;
   std::map<mppp::integer<1>, mppp::rational<1>> den_coeffs;
   orgf operator+(orgf& other);
   orgf operator-(orgf& other);
   orgf operator*(orgf& other);
   orgf operator/(orgf& other);
   
   orgf f1_minus_inv();
   std::string to_string();
};

