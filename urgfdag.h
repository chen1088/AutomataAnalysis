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
        for (auto child : children) {
            if(child->ref_count == 1) {
                delete child;
            } else {
                child->ref_count--;
            }
        }
        children.clear();
    }
    urgf resolvetourgf_nocache()
    {
        // Resolve the urgf tree to a single urgf without caching.
        // This function is not implemented yet.
        switch(operation){
            case urgf_operation::ADD:
            {
                // adding all children
                if (children.size() == 0) {
                    cout <<"Error: ADD operation with no children." << endl;
                    return urgf::getinstance().empty();
                }
                urgf result = children[0]->resolvetourgf_nocache();
                for (int i = 1; i < children.size(); i++) {
                    result = result + children[i]->resolvetourgf_nocache();
                }
                return result;
            }
            case urgf_operation::MULTIPLY:
            {
                // multiplying all children
                if (children.size() == 0) {
                    cout <<"Error: MULTIPLY operation with no children." << endl;
                    return urgf::getinstance().empty();
                }
                urgf result = children[0]->resolvetourgf_nocache();
                for (int i = 1; i < children.size(); i++) {
                    result = result * children[i]->resolvetourgf_nocache();
                }
                return result;
            }
            case urgf_operation::ONEMINUSINVERSE:
            {
                // one minus inverse of the child
                if (children.size() != 1) {
                    cout <<"Error: ONEMINUSINVERSE operation with more than one child." << endl;
                    return urgf::getinstance().empty();
                }
                urgf child_urgf = children[0]->resolvetourgf_nocache();
                return child_urgf.f1_minus_inv();
            }
            case urgf_operation::ATOMX:
            {
                return urgf::getinstance().atomx();
            }
            case urgf_operation::ATOMY:
            {
                return urgf::getinstance().atomy();
            }
            case urgf_operation::EMPTY:
                return urgf::getinstance().empty();
            default:
                throw std::runtime_error("Unknown operation in urgfdag.");
        }
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
                // we assume there is at least one child
                if (children.size() == 0) {
                    cout <<"Error: ADD operation with no children." << endl;
                    return urgf::getinstance().empty();
                }
                urgf result = children[0]->resolvetourgf();
                for (int i = 1; i < children.size(); i++) {
                    result = result + children[i]->resolvetourgf();
                    children[i]->resolved_count++;
                    if(children[i]->resolved_count == children[i]->ref_count) {
                        children[i]->clear();
                    }
                }
                urgf_instance = result;
                is_resolved = true;
                return result;
            }
            case urgf_operation::MULTIPLY:
            // multiplying all children by sequence
            {
                // we assume there is at least one child
                if (children.size() == 0) {
                    cout <<"Error: MULTIPLY operation with no children." << endl;
                    return urgf::getinstance().empty();
                }
                urgf result = children[0]->resolvetourgf();

                for (int i = 1; i < children.size(); i++) {
                    result = result * (children[i]->resolvetourgf());
                    children[i]->resolved_count++;
                    if(children[i]->resolved_count == children[i]->ref_count) {
                        children[i]->clear();
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
                    cout <<"Error: ONEMINUSINVERSE operation with more than one child." << endl;
                    return urgf::getinstance().empty();
                }
                urgf child_urgf = children[0]->resolvetourgf();
                urgf_instance = child_urgf.f1_minus_inv();
                is_resolved = true;
                children[0]->resolved_count++;
                if(children[0]->resolved_count == children[0]->ref_count) {
                    children[0]->clear();
                }
                return urgf_instance;
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

    static void testfunctionmapping(map<int,vector<int>> &input)
    {
        input[2].push_back(3);
    }

    static void test()
    {
        map<int,vector<int>> testmap;
        testfunctionmapping(testmap);
        cout << testmap[2][0] << endl; // should print 3, since the map is passed by reference
    }
    
};