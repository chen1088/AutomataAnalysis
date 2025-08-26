#include <iostream>
#include <boost/dynamic_bitset.hpp>
//#include <gmp.h>
#include <stdio.h>
#include <iostream>
//#include <mp++/mp++.hpp>
//#include <mgl2/fltk.h>
//#include "urgf.h"
#include "urgfdag.h"
//#include"flint/flint.h"

#include <flint/fmpz_poly.h>
#include <flint/arb_fmpz_poly.h>
#include <flint/fmpq_mpoly.h>
#include <flint/fmpz_mpoly.h>
#include <flint/fmpq_poly.h>
#include <flint/fmpz.h>
#include <flint/arb.h>
#include <flint/acb.h>


//using int_t = mppp::integer<1>;

/*
int graph(mglGraph *gr) {
    gr->Title("MathGL Demo");
    gr->SetOrigin(0, 0);
    gr->SetRanges(0, 10, -2.5, 2.5);
    gr->FPlot("sin(1.7*2*pi*x) + sin(1.9*2*pi*x)", "r-4");
    gr->Axis();
    gr->Grid();
    return 0;
}
*/
int main()
{
    std::cout << "Starting..." << '\n';
 // Initialize FLINT rational polynomial context with 2 variables (x, y)
    fmpq_mpoly_ctx_t ctx;   //context needed to say it has 2 vars under lex order
    fmpq_mpoly_ctx_init(ctx, 2, ORD_LEX);

    // Create the rational polynomial: f(x, y) = x^4 + y^4 - 4*x^2*y^2 + 2*x*y - 1/2
    fmpq_mpoly_t poly1;
    fmpq_mpoly_init(poly1, ctx);
    const char *vars[] = {"x", "y"};
    int r = fmpq_mpoly_set_str_pretty(poly1, "x^4 + y^4 - 4*x^2*y^2 + 2*x*y - 1/2", vars, ctx);
    cout << "Set polynomial: " << fmpq_mpoly_get_str_pretty(poly1, vars, ctx) << endl;

    fmpq_mpoly_t poly2;
    fmpq_mpoly_init(poly2, ctx);
    r = fmpq_mpoly_set_str_pretty(poly2, "x^3 + 3*x*y^2 + 2*x*y - 7", vars, ctx);
    cout << "Set polynomial: " << fmpq_mpoly_get_str_pretty(poly2, vars, ctx) << endl;

    fmpq_mpoly_t poly3;
    fmpq_mpoly_init(poly3, ctx);
    r = fmpq_mpoly_set_str_pretty(poly3, "1", vars, ctx);
    cout << "Set polynomial: " << fmpq_mpoly_get_str_pretty(poly3, vars, ctx) << endl;

    fmpq_mpoly_mul(poly3, poly1, poly2, ctx);

    cout << "Product polynomial: " << fmpq_mpoly_get_str_pretty(poly3, vars, ctx) << endl;

    return 0;
}





