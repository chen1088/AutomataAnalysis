#include<vector>
using namespace std;
enum class urgf_operation{
    ADD,
    SUBTRACT,
    MULTIPLY,
    DIVIDE,
    ONEMINUSINVERSE,
    NONE
};
class urgftree {
public:
    urgftree();
    ~urgftree();
    
    void printTree();

    vector<urgftree*> children;
    urgf_operation operation;
    urgf* urgf_ptr;
};