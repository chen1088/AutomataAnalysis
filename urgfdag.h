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
        map<dynamic_bitset<>,map<dynamic_bitset<>,vector<urgfdag*>>> incoming_trans;
        dynamic_bitset<> db1(4, 0b0010);
        dynamic_bitset<> db2(4, 0b0101);
        incoming_trans[db1][db2]={new urgfdag(urgf_operation::ATOMX),new urgfdag(urgf_operation::ATOMY)};
        incoming_trans[db2][db1].push_back(new urgfdag(urgf_operation::ATOMY));
        cout<<incoming_trans[db2][db1].size()<<endl;
        cout<<incoming_trans.contains(db1);
    }
};