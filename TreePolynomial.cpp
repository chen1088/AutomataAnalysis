#include "TreePolynomial.h"

TreePolynomial& TreePolynomial::operator+(TreePolynomial&& other)
{
   return *this;
}
TreePolynomial& TreePolynomial::operator*(TreePolynomial&& other)
{
	return *this;
}
TreePolynomial& TreePolynomial::operator/(TreePolynomial&& other)
{
	return *this;
}
TreePolynomial& TreePolynomial::pow(const mpz_t& exp)
{
	return *this;
}