#pragma once
#include <map>
#include<flint/fmpz_poly.h>
#include<iostream>
using namespace std;

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
   static void test()
   {
      fmpz_poly_t p1, p2, p3;
      fmpz_poly_init(p1);
      fmpz_poly_init(p2);
      fmpz_poly_init(p3);
      fmpz_poly_set_str(p1, "3  1 2 3");
      fmpz_poly_set_str(p2, "4  1 0 3 4");
      fmpz_poly_print_pretty(p1,"x");
      cout<<endl;
      fmpz_poly_print_pretty(p2,"x");
      cout<<endl;
      fmpz_poly_mul(p3, p1, p2);
      fmpz_poly_gcd(p3,p1,p3);
      fmpz_poly_print_pretty(p3,"x");
   }
};

