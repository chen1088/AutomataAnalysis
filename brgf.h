#pragma once

#include <flint/fmpz_poly.h>
#include <flint/arb_fmpz_poly.h>
#include <flint/fmpz_mpoly.h>
#include <flint/fmpz_mpoly_q.h>
#include <flint/fmpq_poly.h>
#include <flint/fmpz.h>
#include <flint/arb.h>
#include <flint/acb.h>
#include <iostream>
#include <vector>
using namespace std;

// brgf: bivariate rational generating function wrapper
// NOTE: this implementation uses FLINT's fmpq_mpoly_t (rational multivariate polynomials)
// The repository already includes and uses <flint/fmpq_mpoly.h>, so this file follows
// the same API patterns. If you specifically require `fmpz_mpoly_q_t`, tell me and
// I'll adapt — many FLINT installations expose the rational multivariate type as fmpq_mpoly_t.

class brgf
{
public:
   brgf();
   ~brgf();
   static brgf &getinstance()
   {
      static brgf instance;
      return instance;
   }

   // Use FLINT's rational multivariate polynomial type
   fmpz_mpoly_q_t bgf_instance; // rational multivariate polynomial
   fmpz_mpoly_ctx_t ctx;        // context with two variables (x,y)

   // Basic operations
   brgf operator+(const brgf &other) const;
   brgf operator-(const brgf &other) const;
   brgf operator*(const brgf &other) const;
   brgf operator/(const brgf &other) const; // uses fmpz_mpoly_q_div
   bool operator==(const brgf &other) const;
   bool is_zero() const { return fmpz_mpoly_q_is_zero(bgf_instance, ctx); }
   brgf f1_minus_inv() const;               // compute 1/(1 - f)
   const fmpz* get_first_coefficient_in_fmpz() const
   {
      // get the numerator
      auto numerator = fmpz_mpoly_q_numref(bgf_instance);
      // we need to find the largest coefficient of the minimum degree term of the numerator
      // for example, in (3x^2y + 2xy^2 + 5y^3)/(x - y), their degrees are all 3. The largest coefficient among these monomials is 5.
      // the degree is sorted in descending order. So we can just find the first few terms with the same degree as the first term, and return the largest coefficient among them.
      // if the numerator is 0, return 0
      if(fmpz_mpoly_is_zero(numerator, ctx))
         return numerator->coeffs;
      fmpz** term;
      fmpz_t sumofexponent;
      fmpz_t minsumofexponent;
      fmpz_t mincoeff;
      fmpz_init(minsumofexponent);
      term = (fmpz**) flint_malloc(2 * sizeof(fmpz*));
      term[0] = (fmpz*) flint_malloc(sizeof(fmpz));
      term[1] = (fmpz*) flint_malloc(sizeof(fmpz));
      fmpz_init(sumofexponent);
      fmpz_init(mincoeff);
      fmpz_mpoly_get_term_exp_fmpz(term, numerator, 0, ctx);
      fmpz_add(minsumofexponent, term[0], term[1]);
      fmpz_set(mincoeff, numerator->coeffs);
      fmpz* res = numerator->coeffs;
      auto length = numerator->length;
      // flint_printf("Numerator has %d terms.\n", length);
      for(int i = 0; i < length; i++)
      {
         fmpz_mpoly_get_term_exp_fmpz(term, numerator, i, ctx);
         fmpz_add(sumofexponent, term[0], term[1]);
         // fmpz_print(sumofexponent);
         if(fmpz_cmp(sumofexponent, minsumofexponent) < 0)
         {
            fmpz_set(minsumofexponent, sumofexponent);
            fmpz_set(mincoeff, numerator->coeffs + i);
            res = numerator->coeffs + i;
         }
         else if(fmpz_cmp(sumofexponent, minsumofexponent) == 0)
         {
            // same degree, compare coefficients, store the largest one
            if(fmpz_cmpabs(numerator->coeffs + i, mincoeff) > 0)
            {
               fmpz_set(mincoeff, numerator->coeffs + i);
               res = mincoeff;
            }
         }
      }
      free(term[0]);
      free(term[1]);
      free(term);
      return res;
   }

   // Constructors for atoms
   brgf atomx() const; // returns the generating function for x
   brgf atomy() const; // returns the generating function for y
   brgf one() const;   // one generating function
   brgf empty() const; // zero generating function

   void clear();
   const char* to_string() const;

   // Implementations inline
   // (constructor / destructor / ops are below)
   static void test()
   {
      brgf a = brgf::getinstance().atomx();
      brgf b = brgf::getinstance().atomy();
      brgf bb = b + b; // now b = 2y
      brgf c = (a + bb).f1_minus_inv()*a;
      brgf d = (c.f1_minus_inv() + a)*a;
      auto res = d.get_first_coefficient_in_fmpz();
      fmpz_print(res);
      const char* d_str = d.to_string();
      std::cout << d_str << std::endl;
   }
};

// Implementations (inlined)
inline brgf::brgf()
{
   // initialize context for 2 variables (x,y)
   fmpz_mpoly_ctx_init(ctx, 2, ORD_LEX);
   fmpz_mpoly_q_init(bgf_instance, ctx);
}

inline brgf::~brgf()
{
   // fmpz_mpoly_q_clear(bgf_instance, ctx);
   fmpz_mpoly_ctx_clear(ctx);
}

inline brgf brgf::atomx() const
{
   brgf result;
   const char *vars[] = {"x", "y"};
   fmpz_mpoly_q_set_str_pretty(result.bgf_instance, "x", vars, result.ctx);
   return result;
}

inline brgf brgf::atomy() const
{
   brgf result;
   const char *vars[] = {"x", "y"};
   fmpz_mpoly_q_set_str_pretty(result.bgf_instance, "y", vars, result.ctx);
   return result;
}

inline brgf brgf::one() const
{
   brgf result;
   const char *vars[] = {"x", "y"};
   fmpz_mpoly_q_set_str_pretty(result.bgf_instance, "1", vars, result.ctx);
   return result;
}

inline brgf brgf::empty() const
{
   brgf result;
   const char *vars[] = {"x", "y"};
   fmpz_mpoly_q_set_str_pretty(result.bgf_instance, "0", vars, result.ctx);
   return result;
}

inline void brgf::clear()
{
   fmpz_mpoly_q_clear(bgf_instance, ctx);
   fmpz_mpoly_q_init(bgf_instance, ctx);
   // fmpz_mpoly_q_set_str_pretty(bgf_instance, "0", (const char *[]){"x", "y"}, ctx);
}

inline const char* brgf::to_string() const
{
   // TODO: this fmpz_mpoly_q_get_str_pretty behaves weird.
   const char *vars[] = {"x", "y"};
   return fmpz_mpoly_q_get_str_pretty(bgf_instance, vars, ctx);
}

inline brgf brgf::operator+(const brgf &other) const
{
   brgf result;
   fmpz_mpoly_q_add(result.bgf_instance, this->bgf_instance, other.bgf_instance, ctx);
   return result;
}

inline brgf brgf::operator-(const brgf &other) const
{
   brgf result;
   fmpz_mpoly_q_sub(result.bgf_instance, this->bgf_instance, other.bgf_instance, ctx);
   return result;
}

inline brgf brgf::operator*(const brgf &other) const
{
   brgf result;
   fmpz_mpoly_q_mul(result.bgf_instance, this->bgf_instance, other.bgf_instance, ctx);
   return result;
}

inline brgf brgf::operator/(const brgf &other) const
{
   brgf result;
   fmpz_mpoly_q_div(result.bgf_instance, this->bgf_instance, other.bgf_instance, ctx);
   return result;
}

inline bool brgf::operator==(const brgf &other) const
{
   return fmpz_mpoly_q_equal(this->bgf_instance, other.bgf_instance, ctx);
}
inline brgf brgf::f1_minus_inv() const
{
   brgf result;
   fmpz_mpoly_q_t one, temp;
   fmpz_mpoly_q_init(one, ctx);
   fmpz_mpoly_q_one(one, ctx);
   fmpz_mpoly_q_init(temp, ctx);
   if (fmpz_mpoly_q_is_one(this->bgf_instance, ctx))
   {
      cout << "Error: cannot compute f1_minus_inv for 1." << endl;
      fmpz_mpoly_q_clear(one, ctx);
      fmpz_mpoly_q_clear(temp, ctx);
      return result;
   }
   fmpz_mpoly_q_sub(temp, one, this->bgf_instance, ctx);
   fmpz_mpoly_q_inv(result.bgf_instance, temp, ctx);
   fmpz_mpoly_q_clear(one, ctx);
   fmpz_mpoly_q_clear(temp, ctx);
   return result;
}
