#include "urgf.h"

urgf::urgf()
{
}

urgf::~urgf()
{
}

urgf urgf::operator+(urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) + g2(x) = (g1(x)h2(x) + g2(x)h1(x))/(h1(x)h2(x))
    urgf result;
    fmpz_poly_t temp1, temp2;
    fmpz_poly_t temp3, temp4;
    fmpz_poly_mul(temp1, this->numerator,other.denominator);
    fmpz_poly_mul(temp2, other.numerator, this->denominator);
    fmpz_poly_add(result.numerator, temp1, temp2);
    fmpz_poly_mul(result.denominator, this->denominator, other.denominator);
    fmpz_poly_gcd(temp3, result.numerator, result.denominator);
    fmpz_poly_div(result.numerator, result.numerator, temp3);
    fmpz_poly_div(result.denominator, result.denominator, temp3);
    return result;    
}
urgf urgf::operator*(urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) * g2(x) = g1(x)g2(x)/h1(x)h2(x)
    urgf result;
    fmpz_poly_t temp1, temp2;
    fmpz_poly_mul(temp1, this->numerator, other.numerator);
    fmpz_poly_mul(result.numerator, temp1, other.numerator);
    fmpz_poly_mul(result.denominator, this->denominator, other.denominator);
    fmpz_poly_gcd(temp2, result.numerator, result.denominator);
    fmpz_poly_div(result.numerator, result.numerator, temp2);
    fmpz_poly_div(result.denominator, result.denominator, temp2);
    return result;
}
urgf urgf::operator-(urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) - g2(x) = (g1(x)h2(x) - g2(x)h1(x))/(h1(x)h2(x))
    urgf result;
    fmpz_poly_t temp1, temp2;
    fmpz_poly_t temp3, temp4;
    fmpz_poly_mul(temp1, this->numerator, other.denominator);
    fmpz_poly_mul(temp2, other.numerator, this->denominator);
    fmpz_poly_sub(result.numerator, temp1, temp2);
    fmpz_poly_mul(result.denominator, this->denominator, other.denominator);
    fmpz_poly_gcd(temp3, result.numerator, result.denominator);
    fmpz_poly_div(result.numerator, result.numerator, temp3);
    fmpz_poly_div(result.denominator, result.denominator, temp3);
    return result;    
}
