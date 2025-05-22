#include<vector>
using namespace std;
enum class urgf_operation{
    ADD,
    SUBTRACT,
    MULTIPLY,
    DIVIDE,
    ONEMINUSINVERSE,
    ATOMX,
    ATOMY,
};
class urgftree {
public:
    urgftree();
    urgftree(urgf_operation op)
    {
        operation = op;
    }
    ~urgftree();
    urgf* resolvetourgf()
    {
        // Resolve the urgf tree to a single urgf.
        // This function is not implemented yet.
        return nullptr;
    }
    void printTree();

    vector<urgftree*> children;
    urgf_operation operation;
    urgf* urgf_ptr;

};