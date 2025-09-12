#pragma once

#include <map>
#include <flint/fmpz_poly.h>
#include <flint/arb_fmpz_poly.h>
#include <flint/fmpq_mpoly.h>
#include <flint/fmpz_mpoly.h>
#include <flint/fmpq_poly.h>
#include <flint/fmpz.h>
#include <flint/arb.h>
#include <flint/acb.h>
#include <flint/fmpz_poly_q.h>
#include <iostream>
#include <boost/dynamic_bitset.hpp>
#include <vector>
using namespace std;

class urgf
{
   // This is the class of univariate rational generating functions
public:
   urgf();
   ~urgf();
   static urgf &getinstance()
   {
     static urgf instance;
     return instance;
   }

   fmpz_poly_q_t rgf_instance;
   urgf operator+(const urgf& other);
   urgf operator-(const urgf& other);
   urgf operator*(const urgf& other);
   urgf operator/(const urgf& other);
   bool operator==(const urgf& other) const;
   urgf f1_minus_inv();
   urgf atomx();
   urgf atomy();
   urgf atomz();
   urgf one();
   urgf empty();
   void clear();
   std::string to_string();

   static void test()
   {
      urgf a = urgf::getinstance().atomx();
      urgf b = urgf::getinstance().atomy();
      b = b + a;
      urgf c = urgf::getinstance().atomz();
      urgf aa = urgf::getinstance().atomx();
      cout<< "a: " << a.to_string() << endl;
      cout<< "b: " << b.to_string() << endl;
      cout<< "c: " << c.to_string() << endl;
      cout<< "aa: " << aa.to_string() << endl;
      cout << "a==aa: " << (a==aa) << endl;
      cout << "a==b: " << (a==b) << endl;
   }
};

// Implementations (inlined to make header-only)
inline urgf::urgf()
{
   fmpz_poly_q_init(rgf_instance);
}

inline urgf::~urgf()
{
   //fmpz_poly_q_clear(rgf_instance);
}

inline urgf urgf::atomx()
{
   // Create an atom for x
   urgf result;
   fmpz_poly_q_init(result.rgf_instance);
   fmpz_poly_q_set_str(result.rgf_instance, "2  0 1/1  1");
   return result;
}
inline urgf urgf::atomy()
{
   // Create an atom for y (same as x for this univariate class)
   urgf result;
   fmpz_poly_q_init(result.rgf_instance);
   fmpz_poly_q_set_str(result.rgf_instance, "2  0 1/1  1");
   return result;
}
inline urgf urgf::atomz()
{
   // Create an atom for z (same as x for this univariate class)
   urgf result;
   fmpz_poly_q_init(result.rgf_instance);
   fmpz_poly_q_set_str(result.rgf_instance, "2  0 1/1  1");
   return result;
}

inline urgf urgf::one()
{
   // Create a 1 generating function
   urgf result;
   fmpz_poly_q_set_str(result.rgf_instance, "1  1/1");
   return result;
}

inline urgf urgf::empty()
{
   // Create a 0 generating function
   urgf result;
   fmpz_poly_q_set_str(result.rgf_instance, "1  0/1  1");
   return result;
}

inline void urgf::clear()
{
   fmpz_poly_q_clear(rgf_instance);
   fmpz_poly_q_init(rgf_instance);
}

inline std::string urgf::to_string()
{
   // Convert the generating function to a string representation
   return fmpz_poly_q_get_str_pretty(rgf_instance, "x");
}

inline urgf urgf::operator+(const urgf& other)
{
   urgf result;
   fmpz_poly_q_add(result.rgf_instance, this->rgf_instance, other.rgf_instance);
   return result;
}
inline urgf urgf::operator*(const urgf& other)
{
   urgf result;
   fmpz_poly_q_mul(result.rgf_instance, this->rgf_instance, other.rgf_instance);
   return result;
}
inline urgf urgf::operator-(const urgf& other)
{
   urgf result;
   fmpz_poly_q_sub(result.rgf_instance, this->rgf_instance, other.rgf_instance);
   return result;    
}
inline urgf urgf::operator/(const urgf& other)
{
   urgf result;
   fmpz_poly_q_div(result.rgf_instance, this->rgf_instance, other.rgf_instance);
   return result;    
}
inline bool urgf::operator==(const urgf& other) const
{
   return fmpz_poly_q_equal(this->rgf_instance, other.rgf_instance);
}

inline urgf urgf::f1_minus_inv()
{
   urgf result;
   fmpz_poly_q_t temp,one;
   fmpz_poly_q_init(one);
   fmpz_poly_q_one(one);
   fmpz_poly_q_init(temp);
   if(fmpz_poly_q_is_one(this->rgf_instance))
   {
      cout<< "Error: cannot compute f1_minus_inv for 1." << endl;
      return result;
   }
   fmpz_poly_q_sub(temp, one, this->rgf_instance);
   fmpz_poly_q_inv(result.rgf_instance, temp);
   fmpz_poly_q_clear(temp);
   fmpz_poly_q_clear(one);
   return result;
}


