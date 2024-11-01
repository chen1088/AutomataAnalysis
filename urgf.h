#pragma once
#include <map>
#include<flint/fmpz_poly.h>

class urgf
{
   // This is the class of univariate rational generating functions
public:
   urgf();
   ~urgf();
   
   // The following functions are the basic operations on generating functions
   // The functions are overloaded to handle different types of generating functions
   // The functions are implemented
   fmpz_poly_t numerator;
   fmpz_poly_t denominator;
   urgf operator+(urgf& other);
   urgf operator-(urgf& other);
   urgf operator*(urgf& other);
   urgf operator/(urgf& other);
   
   urgf f1_minus_inv();
   std::string to_string();
};

