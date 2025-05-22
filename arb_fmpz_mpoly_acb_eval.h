#include<flint/fmpz_mpoly.h>
#include<flint/arb.h>
#include <flint/fmpq_mpoly.h>
// evaluate a multivariate polynomial at a real point
void arb_fmpz_mpoly_acb_eval(arb_t res, const fmpz_mpoly_t f, const arb_t x, slong prec)
{
    // Evaluate the polynomial at the given point
    arb_fmpz_mpoly_evaluate_acb(res, f, x, prec);
}

void convert_fmpz_to_fmpq_mpoly(fmpq_mpoly_t qpoly, const fmpz_mpoly_t zpoly,
   const fmpq_mpoly_ctx_t qctx, const fmpz_mpoly_ctx_t zctx)
{
   // Initialize the rational polynomial
   fmpq_mpoly_init(qpoly, qctx);

   // Set the content to 1
   fmpq_t content;
   fmpq_init(content);
   fmpq_set_ui(content, 1, 1); // content = 1/1
   fmpq_set(fmpq_mpoly_content(qpoly), content);
   fmpq_clear(content);

   // Copy the integer polynomial part
   fmpz_mpoly_set(fmpq_mpoly_num(qpoly), zpoly, zctx);
}