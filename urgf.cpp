#include "urgf.h"

urgf::urgf()
{
}

urgf::~urgf()
{
}

urgf urgf::operator+(urgf& other)
{
    urgf result;
    fmpz_poly_t temp1, temp2;
    fmpz_poly_mul(temp1, this->numerator,other.denominator);
    fmpz_poly_mul(temp2, other.numerator, this->denominator);
    fmpz_poly_add(result.numerator, temp1, temp2);
    fmpz_poly_mul(result.denominator, this->denominator, other.denominator);
    
    return result;    
}