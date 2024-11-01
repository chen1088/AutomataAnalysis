#pragma once
#include "mpfr.h"
#include <map>
#include<memory>
class Coefflist {
public:
	virtual mpfr_ptr get(mpfr_ptr list);
	virtual void add(const Coefflist * other);
	virtual void mul(const Coefflist* other);
private:
	std::map<mpfr_ptr, Coefflist> list;
};
enum OPERATORTYPE {
	ADD,
	MUL,
	DIV,
	POW,
	ATOM
};
class TreePolynomial
{
public:
	TreePolynomial();
	TreePolynomial(const TreePolynomial& copy);
	TreePolynomial(TreePolynomial&& move);
	TreePolynomial(const Coefflist* coefflist);
	TreePolynomial& operator+(TreePolynomial&& other);
	TreePolynomial& operator*(TreePolynomial&& other);
	TreePolynomial& operator/(TreePolynomial&& other);
	TreePolynomial& pow(const mpz_t& exp);
	void extract(const mpz_t* coeffs, mpz_t& dest);
	void evaluate(const mpfr_ptr values, mpfr_t& result);
	~TreePolynomial();
private:
	std::shared_ptr<TreePolynomial> next;
	OPERATORTYPE operatortype;
	std::shared_ptr<Coefflist> coefflist;
	mpfr_ptr exp;
};
