#pragma once
#include <map>
#include<flint/fmpz_poly.h>
#include<flint/arb_fmpz_poly.h>
#include <flint/fmpq_mpoly.h>
#include <flint/fmpz_mpoly.h>
#include <flint/fmpq_poly.h>
#include <flint/fmpz.h>
#include<flint/arb.h>
#include<flint/acb.h>
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
      // fmpz_poly_t p1, p2, p3;
      // fmpz_poly_init(p1);
      // fmpz_poly_init(p2);
      // fmpz_poly_init(p3);
      // fmpz_poly_set_str(p1, "3  1 2 3");
      // fmpz_poly_set_str(p2, "4  1 0 3 4");
      // fmpz_poly_print_pretty(p1,"x");
      // cout<<endl;
      // fmpz_poly_print_pretty(p2,"x");
      // cout<<endl;
      // fmpz_poly_mul(p3, p1, p2);
      // fmpz_poly_gcd(p3,p1,p3);
      // fmpz_poly_print_pretty(p3,"x");
      // for(int i = 0;i<100;i++)
      // {
      //    fmpz_poly_mul(p3, p1, p3);
      // }
      // fmpz_poly_print_pretty(p3,"x");
      // acb_t res,x;
      // acb_init(res);
      // //acb_init(x);
      // acb_set_d_d(x,1.0,0.5);
      // arb_fmpz_poly_evaluate_acb(res,p3,x,1000);
      // acb_printd(res, 10);

      // Initialize FLINT rational polynomial context with 2 variables (x, y)
      fmpq_mpoly_ctx_t ctx;
      fmpq_mpoly_ctx_init(ctx, 2, ORD_LEX);

      // Create the rational polynomial: f(x, y) = x^4 + y^4 - 4*x^2*y^2 + 2*x*y - 1/2
      fmpq_mpoly_t poly;
      fmpq_mpoly_init(poly, ctx);
      const char *vars[] = {"x", "y"};
      int r = fmpq_mpoly_set_str_pretty(poly, "x^4 + y^4 - 4*x^2*y^2 + 2*x*y - 1/2", vars, ctx);
      cout << "Set polynomial: " << fmpq_mpoly_get_str_pretty(poly, vars, ctx) << endl;
      fmpq_t testnumber;
      fmpq_init(testnumber);
      fmpq_set_si(testnumber, 1, 1);
      fmpq_t testnumber2;
      fmpq_init(testnumber2);
      fmpq_set_si(testnumber2, 1, 2);
      fmpq_mpoly_t testx;
      fmpq_mpoly_init(testx, ctx);
      fmpq_mpoly_evaluate_one_fmpq(testx,poly,0,testnumber,ctx);
      cout<<"Evaluate x: " << fmpq_mpoly_get_str_pretty(testx, vars, ctx) << endl;
      fmpq_t testxy;
      fmpq_init(testxy);
      fmpq* testnumber_array[] = { testnumber, testnumber2 };
      fmpq_mpoly_evaluate_all_fmpq(testxy, testx, testnumber_array, ctx);
      // print testxy
      cout<<"Evaluate y: " << fmpq_get_d(testxy) << endl;
      // Grid setup
      const int Nx = 600, Ny = 600;
      const double x_min = -3.0, x_max = 3.0;
      const double y_min = -3.0, y_max = 3.0;
      const double threshold = 0.01;
      const slong scale = 1000000;

      mglData data(Nx, Ny);

      // Initialize FLINT temporaries
      fmpq_t xval, yval, fval;
      fmpz_t xnum, ynum, denom;
      fmpq_init(xval); fmpq_init(yval); fmpq_init(fval);
      fmpz_init(xnum); fmpz_init(ynum); fmpz_init(denom);
      fmpz_set_si(denom, scale);

      for (int j = 0; j < Ny; ++j) {
         double y_real = y_min + (y_max - y_min) * j / (Ny - 1);
         slong y_scaled = static_cast<slong>(y_real * scale);
         fmpz_set_si(ynum, y_scaled);
         fmpq_set_fmpz_frac(yval, ynum, denom);

         for (int i = 0; i < Nx; ++i) {
               double x_real = x_min + (x_max - x_min) * i / (Nx - 1);
               slong x_scaled = static_cast<slong>(x_real * scale);
               fmpz_set_si(xnum, x_scaled);
               fmpq_set_fmpz_frac(xval, xnum, denom);

               // Step 1: Evaluate at y = yval
               fmpq_mpoly_t fx;
               fmpq_mpoly_init(fx, ctx);
               fmpq_mpoly_evaluate_one_fmpq(fx, poly, 1, yval, ctx);

               // Step 2: Evaluate at x = xval
               fmpq_mpoly_t fconst;
               fmpq_mpoly_init(fconst, ctx);
               fmpq_mpoly_evaluate_one_fmpq(fconst, fx, 0, xval, ctx);

               // Step 3: Extract constant term
               slong nvars = fmpq_mpoly_ctx_nvars(ctx);
               std::vector<slong> expv(nvars, 0);
               fmpq_mpoly_get_term_coeff_fmpq(fval, fconst, 0, ctx);

               double fval_d = fmpq_get_d(fval);
               data.a[i + Nx * j] = (std::fabs(fval_d) < threshold) ? 1.0 : 0.0;

               fmpq_mpoly_clear(fx, ctx);
               fmpq_mpoly_clear(fconst, ctx);
         }
      }

      // // Plot using MathGL
      // mglGraph gr;
      // gr.SetRanges(x_min, x_max, y_min, y_max);
      // gr.Axis("xy");
      // gr.Dens(data, "kw");
      // gr.WriteFrame("fmpq_constant_term_curve.png");

      // // Cleanup
      // fmpz_clear(xnum); fmpz_clear(ynum); fmpz_clear(denom);
      // fmpq_clear(xval); fmpq_clear(yval); fmpq_clear(fval);
      // fmpq_mpoly_clear(poly, ctx);
      fmpq_mpoly_ctx_clear(ctx);


   }
};

