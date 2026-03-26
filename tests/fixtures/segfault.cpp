#include <iostream>

struct Node {
    int value;
    Node* next;
};

Node* create_list(int n) {
    Node* head = nullptr;
    for (int i = n; i > 0; --i) {
        Node* node = new Node{i, head};
        head = node;
    }
    return head;
}

void print_list(Node* head) {
    Node* current = head;
    while (current != nullptr) {
        std::cout << current->value << " -> ";
        current = current->next;
    }
    std::cout << "null" << std::endl;
}

int main() {
    Node* list = create_list(5);
    print_list(list);

    // Deliberately cause a null pointer dereference
    Node* bad_ptr = nullptr;
    std::cout << bad_ptr->value << std::endl;  // SIGSEGV here

    return 0;
}
