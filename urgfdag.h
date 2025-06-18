#include<vector>
#include<iostream>
#include"urgf.h"
#include<boost/dynamic_bitset.hpp>
using namespace std;
using boost::dynamic_bitset;
enum class urgf_operation{
    ADD,
    SUBTRACT,
    MULTIPLY,
    DIVIDE,
    ONEMINUSINVERSE,
    ATOMX,
    ATOMY,
    EMPTY,
};
class urgfdag {
public:
    urgfdag();
    urgfdag(urgf_operation op)
    {
        operation = op;
    }
    ~urgfdag();
    urgf* resolvetourgf()
    {
        // Resolve the urgf tree to a single urgf.
        // This function is not implemented yet.
        return nullptr;
    }
    void printTree();

    vector<urgfdag*> children;
    urgf_operation operation;
    urgf* urgf_ptr;
    static void test()
    {
        dynamic_bitset<> a;
        dynamic_bitset<> b;
        cin >> a >> b;
        cout<< a << " " << b << endl;
    }
};