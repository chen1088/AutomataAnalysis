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
   brgf f1_minus_inv() const;               // compute 1/(1 - f)

   // Constructors for atoms
   brgf atomx() const; // returns the generating function for x
   brgf atomy() const; // returns the generating function for y
   brgf one() const;   // one generating function
   brgf empty() const; // zero generating function

   void clear();
   std::string to_string() const;

   // Implementations inline
   // (constructor / destructor / ops are below)
};

// Implementations (inlined)
inline brgf::brgf()
{
   // initialize context for 2 variables (x,y)
   fmpz_mpoly_ctx_init(ctx, 2, ORD_LEX);
   fmpz_mpoly_q_init(bgf_instance, ctx);
   // set to 0
   const char *vars[] = {"x", "y"};
   fmpz_mpoly_q_set_str_pretty(bgf_instance, "0", vars, ctx);
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

inline std::string brgf::to_string() const
{
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
