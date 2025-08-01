#include "urgf.h"

urgf::urgf()
{
    fmpz_poly_init(numerator);
    fmpz_poly_init(denominator);
}

urgf::~urgf()
{
    // Destructor to clear the numerator and denominator
    fmpz_poly_clear(numerator);
    fmpz_poly_clear(denominator);
}

urgf urgf::atomx()
{
    // Create an atom for x
    urgf result;
    fmpz_poly_set_coeff_ui(result.numerator, 1, 1); // x^1
    fmpz_poly_set_coeff_ui(result.numerator, 0, 0); // x^0
    fmpz_poly_set_coeff_ui(result.denominator, 0, 1); // 1
    return result;
}
urgf urgf::atomy()
{
    // Create an atom for y
    // This is urgf so atomy is atomx
    urgf result;
    fmpz_poly_set_coeff_ui(result.numerator, 1, 1); // x^1
    fmpz_poly_set_coeff_ui(result.numerator, 0, 0); // x^0
    fmpz_poly_set_coeff_ui(result.denominator, 0, 1); // 1
    return result;
}

urgf urgf::empty()
{
    // Create a 0 generating function
    urgf result;
    fmpz_poly_set_coeff_ui(result.numerator, 0, 0); // 0
    fmpz_poly_set_coeff_ui(result.denominator, 0, 1); // 1
    return result;
}
void urgf::clear()
{
    // Clear the numerator and denominator
    fmpz_poly_clear(numerator);
    fmpz_poly_clear(denominator);
}
std::string urgf::to_string()
{
    // Convert the generating function to a string representation
    std::string result = "urgf: ";
    result += fmpz_poly_get_str_pretty(numerator, "x");
    result += " / ";
    result += fmpz_poly_get_str_pretty(denominator, "x");
    return result;
}

urgf urgf::operator+(const urgf& other)
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
urgf urgf::operator*(const urgf& other)
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
urgf urgf::operator-(const urgf& other)
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
urgf urgf::operator/(const urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) / g2(x) = g1(x)h2(x)/(h1(x)g2(x))
    urgf result;
    fmpz_poly_t temp1, temp2;
    fmpz_poly_mul(temp1, this->numerator, other.denominator);
    fmpz_poly_mul(temp2, this->denominator, other.numerator);
    fmpz_poly_set(result.numerator, temp1);
    fmpz_poly_set(result.denominator, temp2);
    fmpz_poly_gcd(temp1, result.numerator, result.denominator);
    fmpz_poly_div(result.numerator, result.numerator, temp1);
    fmpz_poly_div(result.denominator, result.denominator, temp1);
    return result;    
}
urgf urgf::f1_minus_inv()
{
    // f(x) = g(x)/h(x)
    // 1/(1-f(x)) = h(x)/(h(x)-g(x))
    urgf result;
    fmpz_poly_t temp;
    fmpz_poly_sub(temp, this->denominator, this->numerator);
    fmpz_poly_set(result.numerator, this->denominator);
    fmpz_poly_set(result.denominator, temp);
    fmpz_poly_gcd(temp, result.numerator, result.denominator);
    if(fmpz_poly_is_one(temp))
    {
        // if the gcd is one, we do not need to reduce.
        return result;
    }
    fmpz_poly_div(result.numerator, result.numerator, temp);
    fmpz_poly_div(result.denominator, result.denominator, temp);
    return result;
}

void urgf::reduce_factor()
{
    // if the numerator and denominator have a common factor, we divide them from both.
    fmpz_poly_t temp;
    fmpz_poly_gcd(temp, this->numerator, this->denominator);
    if (fmpz_poly_is_one(temp))
    {
        // if the gcd is one, we do not need to reduce.
        return;
    }
    fmpz_poly_div(this->numerator, this->numerator, temp);
    fmpz_poly_div(this->denominator, this->denominator, temp);
}