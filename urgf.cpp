#include "urgf.h"

urgf::urgf()
{
    fmpz_poly_q_init(rgf_instance);
}

urgf::~urgf()
{
    // Destructor to clear the numerator and denominator
    // fmpz_poly_q_clear(rgf_instance);
}

urgf urgf::atomx()
{
    // Create an atom for x
    urgf result;
    fmpz_poly_q_init(result.rgf_instance);
    fmpz_poly_q_set_str(result.rgf_instance, "2  0 1/1  1");
    return result;
}
urgf urgf::atomy()
{
    // Create an atom for y
    // This is urgf so atomy is atomx
    urgf result;
    fmpz_poly_q_init(result.rgf_instance);
    fmpz_poly_q_set_str(result.rgf_instance, "2  0 1/1  1");
    return result;
}

urgf urgf::empty()
{
    // Create a 0 generating function
    urgf result;
    fmpz_poly_q_set_str(result.rgf_instance, "1  0/1  1");
    return result;
}
void urgf::clear()
{
    // Clear the numerator and denominator
    fmpz_poly_q_clear(rgf_instance);
    fmpz_poly_q_init(rgf_instance);
}
std::string urgf::to_string()
{
    // Convert the generating function to a string representation
    return fmpz_poly_q_get_str_pretty(rgf_instance, "x");
}

urgf urgf::operator+(const urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) + g2(x) = (g1(x)h2(x) + g2(x)h1(x))/(h1(x)h2(x))
    urgf result;
    fmpz_poly_q_add(result.rgf_instance, this->rgf_instance, other.rgf_instance);
    return result;
}
urgf urgf::operator*(const urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) * g2(x) = g1(x)g2(x)/h1(x)h2(x)
    urgf result;
    fmpz_poly_q_mul(result.rgf_instance, this->rgf_instance, other.rgf_instance);
    return result;
}
urgf urgf::operator-(const urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) - g2(x) = (g1(x)h2(x) - g2(x)h1(x))/(h1(x)h2(x))
    urgf result;
    fmpz_poly_q_sub(result.rgf_instance, this->rgf_instance, other.rgf_instance);
    return result;    
}
urgf urgf::operator/(const urgf& other)
{
    // f1(x) = g1(x)/h1(x)
    // f2(x) = g2(x)/h2(x)
    // f3(x) = f1(x) / g2(x) = g1(x)h2(x)/(h1(x)g2(x))
    urgf result;
    fmpz_poly_q_div(result.rgf_instance, this->rgf_instance, other.rgf_instance);
    return result;    
}
urgf urgf::f1_minus_inv()
{
    // f(x) = g(x)/h(x)
    // 1/(1-f(x)) = h(x)/(h(x)-g(x))
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
    return result;
}