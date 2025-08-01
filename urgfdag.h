#include<vector>
#include<iostream>
#include"urgf.h"
#include<boost/dynamic_bitset.hpp>
using namespace std;
using boost::dynamic_bitset;
enum class urgf_operation{
    ADD,
    MULTIPLY,
    ONEMINUSINVERSE,
    ATOMX, // 0
    ATOMY, // 1
    EMPTY,
};
class urgfdag {
public:
    urgfdag();
    urgfdag(urgf_operation op)
    {
        operation = op;
    }
    ~urgfdag()
    {
        // Clear the urgf instance if it is resolved.
        if (is_resolved) {
            urgf_instance.clear();
        }
        for (auto& child : children) {
            delete child;
        }
        children.clear();
    }
    urgf resolvetourgf()
    {
        // Resolve the urgf tree to a single urgf.
        // This function is not implemented yet.
        if (is_resolved) {
            return urgf_instance;
        }
        switch(operation){
            case urgf_operation::ADD:
            // adding all children
            {
                urgf result;
                for (auto& child : children) {
                    result = result + child->resolvetourgf();
                    child->resolved_count++;
                    if(child->resolved_count == child->ref_count) {
                        child->clear();
                    }
                }
                urgf_instance = result;
                is_resolved = true;
                return result;
            }
            case urgf_operation::MULTIPLY:
            // multiplying all children by sequence
            {
                urgf result;
                for (auto& child : children) {
                    result = result * child->resolvetourgf();
                    child->resolved_count++;
                    if(child->resolved_count == child->ref_count) {
                        child->clear();
                    }
                }
                urgf_instance = result;
                is_resolved = true;
                return result;
            }
            case urgf_operation::ONEMINUSINVERSE:
            // one minus inverse of the child
            {
                // we assume there is only one child
                if (children.size() != 1) {
                    throw std::runtime_error("ONEMINUSINVERSE operation requires exactly one child.");
                }
                urgf child_urgf = children[0]->resolvetourgf();
                urgf_instance = child_urgf.f1_minus_inv();
                is_resolved = true;
                children[0]->resolved_count++;
                if(children[0]->resolved_count == children[0]->ref_count) {
                    children[0]->clear();
                }
            }
            case urgf_operation::ATOMX:
            // urgf equals x
            {
                urgf_instance = urgf::getinstance().atomx();
                is_resolved = true;
                // atom cannot have children
                return urgf_instance;
            }
            case urgf_operation::ATOMY:
            // urgf equals y
            {
                urgf_instance = urgf::getinstance().atomy();
                is_resolved = true;
                // atom cannot have children
                return urgf_instance;
            }
            case urgf_operation::EMPTY:
            // urgf equals 0
            {
                urgf_instance = urgf::getinstance().empty();
                is_resolved = true;
                // empty cannot have children
                return urgf_instance;
            }
            default:
            throw std::runtime_error("Unknown operation in urgfdag.");
        }
    }
    string to_string()
    {
        // Convert the urgfdag to a string representation.
        // This function is not implemented yet.
        string result = "urgfdag: ";
        switch(operation) {
            case urgf_operation::ADD:
                result += "ADD, ";
                break;
            case urgf_operation::MULTIPLY:
                result += "MULTIPLY, ";
                break;
            case urgf_operation::ONEMINUSINVERSE:
                result += "ONEMINUSINVERSE, ";
                break;
            case urgf_operation::ATOMX:
                result += "ATOMX, ";
                break;
            case urgf_operation::ATOMY:
                result += "ATOMY, ";
                break;
            case urgf_operation::EMPTY:
                result += "EMPTY, ";
                break;
        }
        if(operation == urgf_operation::EMPTY || operation == urgf_operation::ATOMX || operation == urgf_operation::ATOMY) {
            return result + "No children.";
        }
        for (size_t i = 0; i < children.size(); i++)
        {
            result += "Child " + std::to_string(i) + ": " + children[i]->to_string() + ", ";
        }
        return result;
    }
    
    void clear()
    {
        // clear urgf pointer
        urgf_instance.clear();
        is_resolved = false;
    }
    void add_child(urgfdag* child)
    {
        children.push_back(child);
        child->ref_count++;
    }
    vector<urgfdag*> children;
    urgf_operation operation;
    urgf urgf_instance;
    bool is_resolved = false;
    // The reference count for the dag node so we can make decision whether to clear the cache
    int ref_count = 0;
    // Record how many of parents have been resolved.
    int resolved_count = 0;
    
    static void test()
    {
        dynamic_bitset<> a;
        dynamic_bitset<> b;
        cin >> a >> b;
        cout<< a << " " << b << endl;
    }
};